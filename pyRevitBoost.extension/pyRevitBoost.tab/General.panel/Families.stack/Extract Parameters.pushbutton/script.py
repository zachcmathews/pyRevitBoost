# pylint: disable=import-error
from collections import OrderedDict

__doc__ = 'Extract parameters from all families in a directory.'
__author__ = 'Zachary Mathews'
__context__ = 'zerodoc'


def write_tsv(tsv, lines):
    import codecs
    create_header(
        tsv=tsv,
        num_cols=max([len(line.split('\t')) for line in lines])
    )
    with codecs.open(tsv, 'a', encoding='utf_16_le') as f:
        for line in lines:
            f.write(line + '\n')


def create_header(tsv, num_cols):
    import codecs
    import math

    fixed_cols = ['Path', 'Category', 'Family', 'Type']
    param_cols = [
        'Name', 'Type', 'Group', 'Shared', 'Instance',
        'Reporting', 'Value', 'Formula'
    ]
    with codecs.open(tsv, 'w+', encoding='utf_16_le') as f:
        num_param_cols = num_cols - len(fixed_cols)
        cols = fixed_cols + \
            param_cols * int(math.ceil(num_param_cols/len(param_cols)))

        f.write(u'\ufeff')          # little-endian utf-16 byte order mark
        f.write('\t'.join(cols))
        f.write('\n')


def extract_category(family_doc):
    fam = family_doc.OwnerFamily
    return fam.FamilyCategory.Name


def extract_family(family_doc):
    return family_doc.Title.rstrip('.rfa')


def extract_parameters(family_doc):
    from Autodesk.Revit.DB import ParameterType, StorageType

    fm = family_doc.FamilyManager
    types = [t for t in fm.Types]
    params = [p for p in fm.GetParameters() if p.UserModifiable]

    extracted = dict((t.Name, []) for t in types)
    for t in types:
        for p in params:
            formula, value = '', ''
            if p.IsDeterminedByFormula:
                formula = p.Formula
            else:
                if p.StorageType == StorageType.Integer:
                    value = t.AsInteger(p)
                    if p.Definition.ParameterType == ParameterType.YesNo:
                        value = 'Yes' if value == 1 else 'No'
                    else:
                        value = t.AsValueString(p)
                elif p.StorageType == StorageType.Double:
                    value = t.AsValueString(p)
                elif p.StorageType == StorageType.String:
                    val_string = t.AsValueString(p)
                    _string = t.AsString(p)

                    # Escape tabs and new lines
                    if _string:
                        value = _string.replace('\t', '<tab>')\
                                       .replace('\r', '<cr>')\
                                       .replace('\n', '<lf>')
                    else:
                        value = val_string if val_string else ''
                else:
                    value = None

            if value is not None:
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
    import os
    import re
    family_paths = set()
    for root, _, files in os.walk(directory):
        if not any(d in root for d in skip):
            for file in files:
                isFamilyDoc = file.endswith('.rfa')
                isRevision = re.search(r'^.+\.[0-9]+\.rfa$', file) is not None
                if isFamilyDoc and not isRevision:
                    filepath = os.path.join(root, file)
                    family_paths.add(filepath)

    return family_paths


def filter_outdated_paths(paths, tsv):
    import os
    import codecs

    if os.path.isfile(tsv):
        tsv_modified_t = os.path.getmtime(tsv)
        lines = []
        with codecs.open(tsv, 'r', encoding='utf_16_le') as f:
            f.readline()    # remove header
            for line in f.readlines():
                line = line.rstrip('\t\r\n')
                if line:
                    lines.append(line)
    else:
        tsv_modified_t = None
        lines = []

    outdated = []
    for path in paths:
        if not tsv_modified_t or os.path.getmtime(path) > tsv_modified_t:
            outdated.append(path)

    return outdated, lines


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


if __name__ == '__main__':
    import sys
    import shutil
    import rpw
    from pyrevit import forms
    from Autodesk.Revit.Exceptions import (CorruptModelException,
                                           FileAccessException)

    # Pick directory to search
    uiapp = rpw.revit.uiapp
    app = uiapp.Application
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

    # Pick file to save listing in
    tsv = forms.save_file(file_ext='txt', restore_dir=True)
    if not tsv:
        sys.exit()

    # Get paths in selected directory
    paths = get_family_paths(directory, skip=skip_directories)

    # Find lines that need to be updated
    outdated, lines = filter_outdated_paths(paths, tsv)

    cnt = 0
    total = len(outdated)
    with forms.ProgressBar(
        title='{value} of {max_value}',
        cancellable=True
    ) as pb:
        for path in outdated:
            if pb.cancelled:
                break

            # Remove outdated lines
            for line in lines[:]:
                line_path = line.split('\t')[0]
                if path == line_path:
                    lines.remove(line)

            # Add updated lines
            try:
                doc = app.OpenDocumentFile(path)
            except (CorruptModelException, FileAccessException):
                print("The following family is corrupt: " + path)
            else:
                category = extract_category(doc)
                family = extract_family(doc)
                parameters_by_type = extract_parameters(doc)

                for _type, parameters in parameters_by_type.items():
                    line = format_dict_as_tsv(OrderedDict([
                        ('path', path),
                        ('category', category),
                        ('family', family),
                        ('type', _type),
                        ('parameters', parameters)
                    ]))
                    lines.append(line)

                doc.Close(False)
            finally:
                cnt += 1
                pb.update_progress(cnt, total)

        else:
            write_tsv(tsv, lines)
            shutil.copyfile(tsv, tsv+'.old')
