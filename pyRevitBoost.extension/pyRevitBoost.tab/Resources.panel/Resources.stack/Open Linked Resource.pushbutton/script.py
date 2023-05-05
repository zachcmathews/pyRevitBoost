# pylint: disable=import-error
import clr
clr.AddReference('System')

from System import Guid

from itertools import groupby
import shutil
import tempfile
import os

from Autodesk.Revit.DB import (
    BuiltInParameter,
    FamilyInstance,
    ModelPathUtils,
    ParameterType,
)

import rpw
from pyrevit import forms

__doc__ = \
    'Open linked external resources for selected family instances.'
__author__ = 'Zachary Mathews'


def main():
    doc = rpw.revit.doc
    uidoc = rpw.revit.uidoc
    selection = rpw.ui.Selection()
    elements = [
        e for e in selection.get_elements(wrapped=False)
        if type(e) == FamilyInstance
    ]
    if not elements:
        return

    if doc.IsWorkshared:
        model_dir = os.path.dirname(ModelPathUtils.ConvertModelPathToUserVisiblePath(doc.GetWorksharingCentralModelPath()))
    else:
        model_dir = os.path.dirname(PathName)

    resources = set()
    for el in elements:
        resources_param = el.get_Parameter(Guid("0ec6edba-a8e6-4ba6-856c-61a67f7834bb"))
        if not resources_param.AsString():
            continue 

        for r in resources_param.AsString().split(';'):
            file = os.path.normcase(os.path.normpath(os.path.join(model_dir, r)))
            if os.path.exists(file):
                resources.add(file)

    resources = list(resources)
    image_formats = ['.jpg', '.png', '.heic', '.bmp', '.tif', '.raw', '.gif']

    if not resources:
        return
    elif len(resources) == 1:
        selected = resources[0]
    elif (
        len(list(groupby(resources, key=lambda r: os.path.splitext(r)[-1]))) == 1
        and os.path.splitext(resources[0])[-1] in image_formats
    ):
        selected = resources
    else:
        selected = forms.SelectFromList.show(resources, title='Select resource', multiselect=True)

    if not selected:
        return
    
    tempdir = tempfile.mkdtemp()
    tempfiles = []
    for f in selected:
        dst = os.path.join(tempdir, os.path.basename(f))
        shutil.copy(f, dst)
        tempfiles.append(dst)
    
    for ext, files in groupby(tempfiles, key=lambda f: os.path.splitext(f)[-1]):
        if ext in image_formats:
            os.startfile(next(files))
        else:
            for file in files:
                os.startfile(file)


if __name__ == '__main__':
    main()