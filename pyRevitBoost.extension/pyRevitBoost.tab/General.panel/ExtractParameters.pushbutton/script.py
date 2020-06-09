import sys
import os
import re
from collections import OrderedDict
import codecs
import shutil

from Autodesk.Revit.DB import StorageType

import rpw
from pyrevit import forms
from boostutils import get_parameter

__doc__ = '''\
Extract parameters from all families in a directory.
'''
__title__ = 'Extract Family Parameters'
__author__ = 'Zachary Mathews'

uiapp = rpw.revit.uiapp
app = uiapp.Application


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


def extract_category(family_doc):
    fam = family_doc.OwnerFamily
    return fam.FamilyCategory.Name


def extract_family(family_doc):
    return family_doc.Title.rstrip('.rfa')


def extract_parameters(family_doc):
    fm = family_doc.FamilyManager
    types = [t for t in fm.Types]
    params = [p for p in fm.Parameters if p.UserModifiable]

    extracted = dict((t.Name, []) for t in types)
    for t in types:
        for p in params:
            formula, value = '', ''
            if p.IsDeterminedByFormula:
                formula = p.Formula
            else:
                if p.StorageType == StorageType.Integer:
                    value = t.AsInteger(p)
                elif p.StorageType == StorageType.Double:
                    value = t.AsDouble(p)
                elif p.StorageType == StorageType.String:
                    valString = t.AsValueString(p)
                    _string = t.AsString(p)
                    value = valString if valString else _string
                else:
                    value = None

            extracted[t.Name].append(OrderedDict([
                ('name', p.Definition.Name),
                ('type', p.Definition.ParameterType),
                ('group', p.Definition.ParameterGroup),
                ('shared', p.IsShared),
                ('instance', p.IsInstance),
                ('reporting', p.IsReporting),
                ('value', value),
                ('formula', formula)
            ]))

    return extracted


def get_family_paths(directory, skip=[]):
    family_paths = set()
    for root, subdirs, files in os.walk(directory):
        if not any(d in root for d in skip):
            for file in files:
                isFamilyDoc = file.endswith('.rfa')
                isRevision = re.search(r'^.+\.[0-9]+\.rfa$', file) is not None
                if isFamilyDoc and not isRevision:
                    filepath = os.path.join(root, file)
                    family_paths.add(filepath)

    return family_paths


def format_dict_as_tsv(d):
    tsv = []
    for v in d.values():
        if isinstance(v, dict) or isinstance(v, OrderedDict):
            tsv.append(format_dict_as_tsv(v))
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


if __name__ == '__main__':
    directory = forms.pick_folder(title='Please select directory to '
                                        'search for families.')
    if not directory:
        sys.exit()

    # Skip certain directories in search
    skip_directories = []
    skip_directory = forms.pick_folder(title='Exclude a directory?')
    while skip_directory:
        skip_directories.append(skip_directory)
        skip_directory = forms.pick_folder(title='Exclude a directory?')

    paths = get_family_paths(directory, skip=skip_directories)

    tsv = forms.save_file(file_ext='tsv', restore_dir=True)
    with codecs.open(tsv, 'w', encoding='utf8') as f:
        f.write('')

    cnt = 0
    total = len(paths)
    failed = []
    with forms.ProgressBar(
        title='{value} of {max_value}',
        cancellable=True
    ) as pb:
        max_num_parameters = 0
        for path in paths:
            doc = app.OpenDocumentFile(path)
            category = extract_category(doc)
            family = extract_family(doc)
            parameters_by_type = extract_parameters(doc)

            with codecs.open(tsv, 'a', encoding='utf8') as f:
                for type, parameters in parameters_by_type.items():
                    max_num_parameters = (
                        len(parameters)
                        if len(parameters) > max_num_parameters
                        else max_num_parameters
                    )

                    line = format_dict_as_tsv(OrderedDict([
                        ('path', path),
                        ('category', category),
                        ('family', family),
                        ('type', type),
                        ('parameters', format_list_as_tsv(parameters))
                    ]))
                    f.write(line + '\n')

            doc.Close(False)

            cnt += 1
            pb.update_progress(cnt, total)
            if pb.cancelled:
                break

        create_header(tsv, num_parameters=max_num_parameters)
        shutil.copyfile(tsv, tsv+'.old')

    if failed:
        forms.alert(
            title='Error: Family could not be loaded',
            msg='\n'.join(failed)
        )
