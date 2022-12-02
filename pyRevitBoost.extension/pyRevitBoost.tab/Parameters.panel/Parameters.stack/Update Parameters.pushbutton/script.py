# pylint: disable=import-error
import sys
import os
import codecs
from collections import OrderedDict

from Autodesk.Revit.DB import (BuiltInParameterGroup, ParameterType,
                               StorageType, UnitFormatUtils)
from Autodesk.Revit.Exceptions import (CorruptModelException,
                                       FileAccessException)

import rpw
from pyrevit import forms
from boostutils import memoize

__doc__ = 'Update parameters for all families in a directory.'
__author__ = 'Zachary Mathews'
__context__ = 'zero-doc'

uiapp = rpw.revit.uiapp
app = uiapp.Application


def diff_tsv(old, new):
    def _preprocess(line):
        line = line.rstrip('\t\r\n')\
                   .replace('TRUE', 'True')\
                   .replace('FALSE', 'False')

        line_cols = line.split('\t')
        for i, _ in enumerate(line_cols):
            if (
                line_cols[i].startswith('"')
                and line_cols[i].endswith('"')
            ):
                line_cols[i] = line_cols[i][1:-1]
                line_cols[i] = line_cols[i].replace('""', '"')

        line = '\t'.join(line_cols)
        return line

    old_lines = []
    with codecs.open(old, 'r', encoding='utf_16_le') as f:
        f.readline()
        for line in f.readlines():
            line = _preprocess(line)
            if line:
                old_lines.append(line)

    updated_lines = []
    with codecs.open(new, 'r', encoding='utf_16_le') as f:
        f.readline()
        for line in f.readlines():
            line = _preprocess(line)
            if line and line not in old_lines:
                updated_lines.append(line)

    return old_lines, updated_lines


def update_old_tsv(tsv, families):
    max_num_parameters = 0
    with codecs.open(tsv, 'w', encoding='utf_16_le') as f:
        for _, family in families.items():
            for _type in family:
                line = format_dict_as_tsv(_type)
                f.write(line + '\n')

                num_parameters = len(_type['parameters'])
                if num_parameters > max_num_parameters:
                    max_num_parameters = num_parameters

    create_header(tsv=tsv, num_parameters=max_num_parameters)


def create_header(tsv, num_parameters):
    lines = []
    with codecs.open(tsv, 'r', encoding='utf_16_le') as f:
        for line in f.readlines():
            lines.append(line)

    with codecs.open(tsv, 'w', encoding='utf_16_le') as f:
        # Prepend little-endian utf-16 byte order mark
        f.write(u'\ufeff')

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


def format_list_as_tsv(_list):
    tsv = []
    for i in _list:
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
        ('type', values[3] if len(values) > 3 else ' '),
        ('parameters', [])
    ])

    parameter_cols = [
        'name', 'type', 'group', 'shared',
        'instance', 'reporting', 'value', 'formula'
    ]
    for i in range(4, len(values), len(parameter_cols)):
        param = OrderedDict()
        for j, col_name in enumerate(parameter_cols):
            if i+j < len(values):
                value = values[i+j]
                param[col_name] = value
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
            # shared params files are utf_16
            name = definition.Name
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
            p = create_parameter(
                family_manager,
                name,
                group,
                _type,
                isShared,
                isInstance
            )
        else:
            p = family_params[name]

        update_properties(family_manager, p, group, isInstance, isReporting)

        if formula:
            update_formula(family_manager, p, formula)
        elif value:
            update_value(
                family_manager,
                family_manager.CurrentType,
                p,
                value,
                units
            )

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
        if p.Definition.ParameterType == ParameterType.YesNo:
            value = 1 if value == 'Yes' else 0
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
                family_manager.SetFormula(p, None)
                family_manager.Set(p, value)
        else:
            raise ValueError

    elif p.StorageType == StorageType.String:
        _str = family_type.AsString(p)
        _value_str = family_type.AsValueString(p)
        current_value = _value_str if _value_str else _str if _str else ''
        current_value = current_value.replace('\t', '<tab>')

        if value != current_value:
            value = value.replace('<tab>', '\t')\
                         .replace('<cr>', '\r')\
                         .replace('<lf>', '\n')
            family_manager.Set(p, value)

    else:
        raise TypeError


def update_formula(family_manager, p, formula):
    if formula != p.Formula:
        family_manager.SetFormula(p, formula)


def update_properties(family_manager, p, group, isInstance, isReporting):
    if p.Definition.ParameterGroup != group:
        p.Definition.ParameterGroup = group

    if hasattr(p.Definition, 'BuiltInParameter') and not p.Definition.BuiltInParameter:
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


if __name__ == '__main__':  # noqa: C901
    new = forms.pick_file(file_ext='txt', restore_dir=True)
    if not new:
        sys.exit()

    old = new + '.old'
    if not os.path.exists(old):
        forms.alert(
            title='No old file found',
            msg='An existing parameters file is required to use this command. '
                'Generate one using the extract parameters command.',
            exitscript=True
        )

    old_lines, updated_lines = diff_tsv(old=old, new=new)
    if not updated_lines:
        forms.alert(
            title='No updates found',
            msg='Could not find any updates in the provided tsv file.',
            exitscript=True
        )

    parsed_old_lines = [parse_line(line) for line in old_lines]
    existing_fams = group_by_path(parsed_old_lines)
    parsed_updated_lines = [parse_line(line) for line in updated_lines]
    updated_fams = group_by_path(parsed_updated_lines)
    selected_updates = forms.SelectFromList.show(
        title='Apply updates',
        context=updated_fams.keys(),
        multiselect=True,
        width=800
    )
    if not selected_updates:
        sys.exit()

    cnt = 0
    total = len(updated_fams)
    with forms.ProgressBar(
        title='{value} of {max_value}',
        cancellable=True
    ) as pb:
        for path in selected_updates:
            if pb.cancelled:
                break

            try:
                doc = app.OpenDocumentFile(path)
            except (CorruptModelException, FileAccessException):
                print("The following family is corrupt: " + path)
            else:
                family_manager = doc.FamilyManager

                with rpw.db.Transaction('Update family', doc=doc):
                    family_types = updated_fams[path]
                    for _type in family_types:
                        activate_family_type(
                            family_manager,
                            name=_type['type']
                        )
                        update_parameters(
                            family_manager=family_manager,
                            parameters=_type['parameters'],
                            units=doc.GetUnits()
                        )

                        # Update old tsv entry or add new entry
                        for i in range(len(existing_fams[path])):
                            if existing_fams[path][i]['type'] == _type['type']:
                                existing_fams[path][i] = _type
                                break
                        else:
                            existing_fams[path].append(_type)

                doc.Close(True)
            finally:
                cnt += 1
                pb.update_progress(cnt, total)

        update_old_tsv(tsv=old, families=existing_fams)
