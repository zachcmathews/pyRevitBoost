# pylint: disable=import-error
import os
import sys
import re

from Autodesk.Revit.Exceptions import (CorruptModelException,
                                       FileAccessException)

import rpw
from pyrevit import forms

__doc__ = 'Upgrade all families in a directory to the current Revit version.'
__author__ = 'Zachary Mathews'
__context__ = 'zerodoc'

uiapp = rpw.revit.uiapp
app = uiapp.Application


def get_family_paths(directory):
    family_paths = set()
    for root, _, files in os.walk(directory):
        for file in files:
            isFamilyDoc = file.endswith('.rfa')
            isRevision = re.search(r'^.+\.[0-9]+\.rfa$', file) is not None
            if isFamilyDoc and not isRevision:
                filepath = os.path.join(root, file)
                family_paths.add(filepath)

    return family_paths


def get_revision_paths(directory):
    for root, _, files in os.walk(directory):
        for file in files:
            isFamilyDoc = file.endswith('.rfa')
            isRevision = re.search(r'^.+\.[0-9]+\.rfa$', file) is not None
            if isFamilyDoc and isRevision:
                filepath = os.path.join(root, file)
                yield filepath


if __name__ == '__main__':
    directory = forms.pick_folder(title='Please select directory to '
                                        'search for families.')
    if not directory:
        sys.exit()

    paths = get_family_paths(directory)

    cnt = 0
    total = len(paths)
    with forms.ProgressBar(
        title='{value} of {max_value}',
        cancellable=True
    ) as pb:
        for path in paths:
            if pb.cancelled:
                break

            try:
                doc = app.OpenDocumentFile(path)
                doc.Close(True)
            except (CorruptModelException, FileAccessException):
                print("The following family is corrupt: " + path)
            finally:
                cnt += 1
                pb.update_progress(cnt, total)

    should_remove_previous_revisions = forms.alert(
        title='Remove previous versions?',
        msg='Remove previous versions?',
        ok=False,
        yes=True,
        no=True,
        exitscript=True
    )
    if should_remove_previous_revisions:
        for revision_path in get_revision_paths(directory):
            os.remove(revision_path)
