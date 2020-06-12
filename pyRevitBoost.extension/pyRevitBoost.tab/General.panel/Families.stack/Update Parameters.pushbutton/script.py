import sys
import os
import math
import codecs
from collections import OrderedDict

from Autodesk.Revit.DB import (BuiltInParameterGroup, ParameterType,
                               StorageType, UnitFormatUtils)

import rpw
from pyrevit import forms
from boostutils import memoize

__doc__ = '''\
Update parameters for all families in a directory.
'''
__author__ = 'Zachary Mathews'
__context__ = 'zerodoc'

uiapp = rpw.revit.uiapp
app = uiapp.Application


def diff_tsv(old, new):
    old_lines = []
    with codecs.open(old, 'r', encoding='utf8') as f:
        f.readline()    # don't care about header
        for line in f.readlines():
            line = line.rstrip('\t\n')
            if line:
                old_lines.append(line)

    updated_lines = []
    with codecs.open(new, 'r', encoding='utf8') as f:
        f.readline()    # don't care about header
        for line in f.readlines():
            line = line.rstrip('\t\r\n')\
                       .replace('TRUE', 'True')\
                       .replace('FALSE', 'False')

            if line and line not in old_lines:
                updated_lines.append(line)

    return (old_lines, updated_lines)


def create_header(tsv, num_parameters):
    lines = []
    with codecs.open(tsv, 'r', encoding='utf8') as f:
        for line in f.readlines():
            lines.append(line)

    with codecs.open(tsv, 'w', encoding='utf8') as f:
        # Prepend header
        parameter_cols = [
            'Name', 'Type', 'Group', 'Shared', 'Instance',
            'Reporting', 'Value', 'Formula'
        ] * num_parameters
        cols = ['Path', 'Category', 'Family', 'Type'] + parameter_cols
        f.write('\t'.join(cols))
        f.write('\n')

        # Write data back
        f.write(''.join(lines))


def update_old_tsv(tsv, families):
    max_num_parameters = 0
    with codecs.open(tsv, 'w', encoding='utf8') as f:
        for path, family in families.items():
            for type in family:
                line = format_dict_as_tsv(OrderedDict([
                    ('path', type['path']),
                    ('category', type['category']),
                    ('family', type['family']),
                    ('type', type['type']),
                    ('parameters', type['parameters']),
                ]))
                f.write(line + '\n')

                if len(type['parameters']) > max_num_parameters:
                    max_num_parameters = len(type['parameters'])

    create_header(tsv, num_parameters=max_num_parameters)


def format_dict_as_tsv(d):
    tsv = []
    for v in d.values():
        if isinstance(v, dict) or isinstance(v, OrderedDict):
            tsv.append(format_dict_as_tsv(v))
        elif isinstance(v, list):
            tsv.append(format_list_as_tsv(v))
        else:
            tsv.append(str(v))

    return '\t'.join(tsv)


def format_list_as_tsv(l):
    tsv = []
    for i in l:
        if isinstance(i, dict) or isinstance(i, OrderedDict):
            tsv.append(format_dict_as_tsv(i))
        else:
            tsv.append(str(i))

    return '\t'.join(tsv)


def parse_line(line):
    values = line.split('\t')
    d = OrderedDict([
        ('path', values[0]),
        ('category', values[1]),
        ('family', values[2]),
        ('type', values[3] if len(values) > 3 else ' '),    # Gsheets strips spaces
        ('parameters', [])
    ])

    parameter_cols = [
        'name', 'type', 'group', 'shared', 'instance',
        'reporting', 'value', 'formula'
    ]
    num_parameters = math.ceil(float(len(values)-4)/len(parameter_cols))
    for i in range(4, 4 + int(num_parameters*len(parameter_cols)), len(parameter_cols)):
        param = OrderedDict()
        for j, col_name in enumerate(parameter_cols):
            if i+j < len(values):
                # Formulas evaluating to text have to be wrapped,
                # otherwise Google Sheets strips quotes
                if col_name == 'formula':
                    value = values[i+j]
                    if value.startswith('<text>') and value.endswith('</text>'):
                        value = value.lstrip('<text>').rstrip('</text>')

                param[col_name] = values[i+j]
            else:
                param[col_name] = ''

        d['parameters'].append(param)

    return d


def group_by_path(parsed_lines):
    groups = OrderedDict()
    for line in parsed_lines:
        if line['path'] in groups:
            groups[line['path']].append(line)
        else:
            groups[line['path']] = [line]

    return groups


def activate_family_type(family_manager, name):
    family_types = [t for t in family_manager.Types]
    family_type = get_family_type(
        name=name,
        family_types=family_types
    )
    if not family_type:
        family_type = make_family_type(
            family_manager=family_manager,
            name=name
        )

    family_manager.CurrentType = family_type


def get_family_type(name, family_types):
    for family_type in family_types:
        if family_type.Name == name:
            return family_type


def make_family_type(family_manager, name):
    return family_manager.NewType(name)


def get_parameters(family_manager):
    params = OrderedDict()
    for param in family_manager.GetParameters():
        params[param.Definition.Name] = param

    return params


@memoize
def get_shared_parameters():
    file = app.OpenSharedParameterFile()

    shared_parameters = {}
    for group in file.Groups:
        for definition in group.Definitions:
            # shared params files are utf16
            name = definition.Name.decode('utf-8', 'replace')
            shared_parameters[name] = definition

    return shared_parameters


def update_parameters(family_manager, parameters, units):
    family_params = get_parameters(family_manager)
    sorted_params = OrderedDict()
    for param in parameters:
        name = param['name']
        _type = getattr(ParameterType, param['type'])
        group = getattr(BuiltInParameterGroup, param['group'])
        isShared = param['shared'] == 'True'
        isInstance = param['instance'] == 'True'
        isReporting = param['reporting'] == 'True'
        value = param['value']
        formula = param['formula']

        if name not in family_params.keys():
            p = create_parameter(family_manager, name, group, _type, isShared, isInstance)
        else:
            p = family_params[name]

        update_properties(family_manager, p, group, isInstance, isReporting)

        if formula:
            update_formula(family_manager, p, formula)
        elif value:
            update_value(family_manager, family_manager.CurrentType, p, value, units)

        sorted_params[name] = p

    # Add in non-usermodifiable parameters before reordering
    for param in family_params:
        if param not in sorted_params:
            sorted_params[param] = family_params[param]
    reorder_parameters(family_manager, sorted_params)


def create_parameter(family_manager, name, group, _type, isShared, isInstance):
    if isShared:
        shared_params = get_shared_parameters()
        shared_param = shared_params[name]
        return family_manager.AddParameter(
            shared_param,
            group,
            isInstance
        )
    else:
        return family_manager.AddParameter(
            name,
            group,
            _type,
            isInstance
        )


def update_value(family_manager, family_type, p, value, units):
    '''
    Updating values is very slow (0.15s/update). Do as few as possible.
    '''
    if p.StorageType == StorageType.Integer:
        if int(value) != family_type.AsInteger(p):
            family_manager.Set(p, int(value))

    elif p.StorageType == StorageType.Double:
        (success, value) = UnitFormatUtils.TryParse(
            units,
            p.Definition.UnitType,
            value
        )
        if success:
            if value != family_type.AsDouble(p):
                family_manager.Set(p, value)
        else:
            raise ValueError

    elif p.StorageType == StorageType.String:
        _str = family_type.AsString(p)
        _value_str = family_type.AsValueString(p)
        current_value = _value_str if _value_str else _str

        if value != current_value:
            family_manager.Set(p, value)

    else:
        raise TypeError


def update_formula(family_manager, p, formula):
    if formula != p.Formula:
        family_manager.SetFormula(p, formula)


def update_properties(family_manager, p, group, isInstance, isReporting):
    if p.Definition.ParameterGroup != group:
        p.Definition.ParameterGroup = group

    if isInstance:
        family_manager.MakeInstance(p)
    else:
        family_manager.MakeType(p)

    if isReporting:
        family_manager.MakeReporting(p)
    else:
        family_manager.MakeNonReporting(p)


def reorder_parameters(family_manager, sorted_params):
    # I don't know why I can't just use sorted_params, but I can't
    ordered_params = sorted(
        family_manager.GetParameters(),
        key=lambda p: sorted_params.keys().index(p.Definition.Name)
    )
    family_manager.ReorderParameters(ordered_params)


if __name__ == '__main__':
    new = forms.pick_file(file_ext='tsv', restore_dir=True)
    if not new:
        sys.exit()

    old = new + '.old'
    if not os.path.exists(old):
        forms.alert(
            title='No old file found',
            msg='An existing parameters file is required to use this command, '
                'otherwise compute time will be very long.\n\n'
                'Generate one using the extract parameters command.',
            exitscript=True
        )

    (old_lines, updated_lines) = diff_tsv(old=old, new=new)
    if not updated_lines:
        forms.alert(
            title='No updates found',
            msg='Could not find any updates in the provided tsv file.',
            exitscript=True
        )

    parsed_old_lines = [parse_line(l) for l in old_lines]
    existing_families = group_by_path(parsed_old_lines)
    parsed_updated_lines = [parse_line(l) for l in updated_lines]
    updated_families = group_by_path(parsed_updated_lines)
    selected_updates = forms.SelectFromList.show(
        title='Apply updates',
        context=updated_families.keys(),
        multiselect=True
    )

    sys.exit()
    cnt = 0
    total = len(updated_families)
    failed = []
    with forms.ProgressBar(
        title='{value} of {max_value}',
        cancellable=True
    ) as pb:
        for path in existing_families.keys():
            if path not in selected_updates:
                continue

            doc = app.OpenDocumentFile(path)
            family_manager = doc.FamilyManager

            with rpw.db.Transaction('Update family', doc=doc):
                family_types = updated_families[path]
                for type in family_types:
                    activate_family_type(family_manager, name=type['type'])
                    update_parameters(
                        family_manager=family_manager,
                        parameters=type['parameters'],
                        units=doc.GetUnits()
                    )

            doc.Close(True)

            existing_families[path] = updated_families[path]
            cnt += 1
            pb.update_progress(cnt, total)
            if pb.cancelled:
                break

    update_old_tsv(old, existing_families)

    if failed:
        forms.alert(
            title='Error: Family could not be loaded',
            msg='\n'.join(failed)
        )
