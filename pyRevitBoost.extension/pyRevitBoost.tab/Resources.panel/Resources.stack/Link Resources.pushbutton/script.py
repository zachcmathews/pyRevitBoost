# pylint: disable=import-error
import clr
clr.AddReference('PresentationCore')
clr.AddReference('System.Drawing.Primitives')
clr.AddReference('System.Runtime')

from System import Guid
from System.IO import MemoryStream
from System.Windows import DataFormats
from System.Windows.Media.Imaging import BitmapImage

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
    'Link external resources for selected family instances.'
__author__ = 'Zachary Mathews'


class Form(forms.WPFWindow):
    def __init__(self, elements):
        forms.WPFWindow.__init__(self, 'form.xaml')
        self.DataContext = self
        self._elements = elements
        self._ok = False
    
    @property
    def elements(self):
        return self._elements
    
    def resource_drop(self, sender, e):
        if not e.Data.GetDataPresent(DataFormats.FileDrop):
            return

        grid = e.OriginalSource
        element = grid.DataContext
        files = e.Data.GetData(DataFormats.FileDrop)
        for file in files:
            element.resources.add(file)
    
    def cancel_click(self, sender, e):
        self._ok = False
        self.Close()

    def ok_click(self, sender, e):
        self._ok = True
        self.Close()

    def show(self):
        self.show_dialog()
        return self._ok, self._elements


class Element():
    def __init__(self, id, thumbnail, family, family_type, tags, resources):
        self._id = id
        self._thumbnail = thumbnail
        self._family = family
        self._family_type = family_type
        self._tags = tags
        self._resources = resources

    @property
    def id(self):
        return self._id

    @property
    def thumbnail(self):
        return self._thumbnail
    
    @property
    def family(self):
        return self._family

    @property
    def family_type(self):
        return self._family_type

    @property
    def tags(self):
        return self._tags
    
    @property
    def resources(self):
        return self._resources


def main():
    doc = rpw.revit.doc
    uidoc = rpw.revit.uidoc
    selection = rpw.ui.Selection()
    selected = [
        e for e in selection.get_elements(wrapped=False)
        if type(e) == FamilyInstance
    ]
    selected_ids = [e.Id for e in selected]

    if doc.IsWorkshared:
        model_dir = os.path.dirname(ModelPathUtils.ConvertModelPathToUserVisiblePath(doc.GetWorksharingCentralModelPath()))
    else:
        model_dir = os.path.dirname(PathName)

    tags = rpw.db.Collector(of_class='IndependentTag').get_elements(wrapped=False)
    tags = [
        t for t in tags
        if t.TaggedLocalElementId in selected_ids
    ]

    elements = []
    for el in selected:
        preview_image = el.Symbol.GetPreviewImage(System.Drawing.Size(300, 300))

        stream = MemoryStream()
        preview_image.Save(stream, System.Drawing.Imaging.ImageFormat.Bmp)

        thumbnail = BitmapImage()
        thumbnail.BeginInit()
        thumbnail.StreamSource = stream
        thumbnail.EndInit()

        resources_param = el.get_Parameter(Guid("0ec6edba-a8e6-4ba6-856c-61a67f7834bb"))
        resources_str = resources_param.AsString()
        if resources_str:
            resources = [os.path.normcase(os.path.normpath(os.path.join(model_dir, r))) for r in resources_str.split(';')]
        else:
            resources = []

        elements.append(Element(
            id=el.Id,
            thumbnail=thumbnail,
            family=el.get_Parameter(
                               getattr(BuiltInParameter, 'ELEM_FAMILY_PARAM')
                           ).AsValueString(),
            family_type=el.get_Parameter(
                               getattr(BuiltInParameter, 'ELEM_TYPE_PARAM')
                           ).AsValueString(),
            tags='; '.join(set(
                t.TagText for t in tags
                if t.TaggedLocalElementId == el.Id
            )),
            resources=set(resources)
        ))

    ok, updated = Form(sorted(elements, key=lambda e: e.tags)).show()
    if not ok:
        return

    with rpw.db.Transaction('Update linked resources', doc=doc):
        for el in updated:
            resources_param = doc.GetElement(el.id).get_Parameter(Guid("0ec6edba-a8e6-4ba6-856c-61a67f7834bb"))
            resources = [os.path.relpath(os.path.realpath(r), start=model_dir) for r in el.resources]
            resources_param.Set(';'.join(resources))


if __name__ == '__main__':
    main()