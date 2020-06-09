import sys
import os
import codecs

from Autodesk.Revit.DB import BuiltInParameterGroup, ParameterType, StorageType

import rpw
from pyrevit import forms
from boostutils import get_parameter

__doc__ = '''\
Update parameters for all families in a directory.
'''
__title__ = 'Update Family Parameters'
__author__ = 'Zachary Mathews'

uiapp = rpw.revit.uiapp
app = uiapp.Application


def get_shared_parameters():
    file = app.OpenSharedParameterFile()

    shared_parameters = {}
    for group in file.Groups:
        for definition in group.Definitions:
            # shared params files are utf16
            name = definition.Name.decode('utf-8', 'replace')
            shared_parameters[name] = definition

    return shared_parameters

def diff_tsv(old, new):
    old_lines = []
    with codecs.open(old, 'r', encoding='utf8') as f:
        f.readline()    # don't care about header
        for line in f.readlines():
            old_lines.append(line.rstrip('\t\n'))

    changed_lines = []
    with codecs.open(new, 'r', encoding='utf8') as f:
        f.readline()    # don't care about header
        for line in f.readlines():
            line = line.rstrip('\r\n')\
                       .replace('TRUE', 'True')\
                       .replace('FALSE', 'False')
            if line not in old_lines and line.split('\t')[0]:
                changed_lines.append(line)

    return changed_lines


def parse_line(line):
    values = line.split('\t')
    d = {
        'path': values[0],
        'category': values[1],
        'family': values[2],
        'type': values[3],
        'parameters': []
    }

    parameter_cols = [
        'name', 'type', 'group', 'shared', 'instance',
        'reporting', 'value', 'formula'
    ]
    for i in range(4, len(values)-len(parameter_cols), len(parameter_cols)):
        if values[i]:   # remove trailing empties
            param = {}
            for j, col_name in enumerate(parameter_cols):
                param[col_name] = values[i+j]

            d['parameters'].append(param)

    return d


def group_by_path(parsed_lines):
    groups = {}
    for line in parsed_lines:
        if line['path'] in groups:
            groups[line['path']].append(line)
        else:
            groups[line['path']] = [line]

    return groups


def get_family_type_by_name(name, family_types):
    for family_type in family_types:
        if family_type.Name == name:
            return family_type


def get_parameters(family_manager):
    params = {}
    for param in family_manager.Parameters:
        params[param.Definition.Name] = param

    return params


def update_parameters(family_manager, parameters):
    family_params = get_parameters(family_manager)
    shared_params = get_shared_parameters()

    for param in parameters:
        name = param['name']
        _type = getattr(ParameterType, param['type'])
        group = getattr(BuiltInParameterGroup, param['group'])
        isSharedParameter = param['shared'] == 'True'
        isInstanceParameter = param['instance'] == 'True'
        isReportingParameter = param['reporting'] == 'True'
        value = param['value']
        formula = param['formula']

        # Make new parameter
        if name not in family_params.keys():
            if isSharedParameter:
                shared_param = shared_params[name]
                p = family_manager.AddParameter(
                    shared_param,
                    group,
                    isInstanceParameter
                )
            else:
                p = family_manager.AddParameter(
                    name,
                    group,
                    _type,
                    isInstanceParameter
                )
        else:
            p = family_params[name]

        # Set value/formula
        if value:
            if p.StorageType == StorageType.Integer:
                family_manager.Set(p, int(value))
            elif p.StorageType == StorageType.Double:
                family_manager.Set(p, float(value))
            elif p.StorageType == StorageType.String:
                family_manager.Set(p, value)
            else:
                value = None
        elif formula:
            family_manager.SetFormula(formula)

        # Set instance/type param
        if isInstanceParameter:
            family_manager.MakeInstance(p)
        else:
            family_manager.MakeType(p)

        # Set reporting/non-reporting
        if isReportingParameter:
            family_manager.MakeReporting(p)
        else:
            family_manager.MakeNonReporting(p)


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

    # Parse tsv
    changed_lines = diff_tsv(old=old, new=new)
    parsed_lines = [parse_line(l) for l in changed_lines]
    changed_families = group_by_path(parsed_lines)

    forms.alert(
        title='Continue?',
        msg=('The following families will be updated:\n' +
             '\n'.join(changed_families)),
        ok=True,
        cancel=True,
        exitscript=True
    )

    cnt = 0
    total = len(changed_families)
    failed = []
    with forms.ProgressBar(
        title='{value} of {max_value}',
        cancellable=True
    ) as pb:
        for path, parsed in changed_families.items():
            doc = app.OpenDocumentFile(path)

            with rpw.db.Transaction('Update family', doc=doc):
                fm = doc.FamilyManager
                family_types = [t for t in fm.Types]
                for line in parsed:
                    family_type = get_family_type_by_name(
                        line['type'],
                        family_types=family_types
                    )
                    fm.CurrentType = family_type
                    update_parameters(
                        family_manager=fm,
                        parameters=line['parameters']
                    )

            doc.Close(True)

            cnt += 1
            pb.update_progress(cnt, total)
            if pb.cancelled:
                break

    if failed:
        forms.alert(
            title='Error: Family could not be loaded',
            msg='\n'.join(failed)
        )
