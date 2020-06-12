import os
import sys
import re

import rpw
from pyrevit import forms

__doc__ = '''\
Upgrade all families in a directory to the current Revit version.
'''
__author__ = 'Zachary Mathews'
__context__ = 'zerodoc'

uiapp = rpw.revit.uiapp
app = uiapp.Application


def get_family_paths(directory):
    family_paths = set()
    for root, subdirs, files in os.walk(directory):
        for file in files:
            isFamilyDoc = file.endswith('.rfa')
            isRevision = re.search(r'^.+\.[0-9]+\.rfa$', file) is not None
            if isFamilyDoc and not isRevision:
                filepath = os.path.join(root, file)
                family_paths.add(filepath)

    return family_paths


if __name__ == '__main__':
    directory = forms.pick_folder(title='Please select directory to '
                                        'search for families.')
    if not directory:
        sys.exit()

    paths = get_family_paths(directory)

    cnt = 0
    total = len(paths)
    failed = []
    with forms.ProgressBar(
        title='{value} of {max_value}',
        cancellable=True
    ) as pb:
        max_num_parameters = 0
        for path in paths:
            try:
                doc = app.OpenDocumentFile(path)
                doc.Close(True)
            except:
                print("The following family is corrupt: " + path)

            cnt += 1
            pb.update_progress(cnt, total)
            if pb.cancelled:
                break

    if failed:
        forms.alert(
            title='Error: Family could not be loaded',
            msg='\n'.join(failed)
        )
