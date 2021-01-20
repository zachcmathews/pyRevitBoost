# pylint: disable=import-error
import sys
import os
from Autodesk.Revit.DB import FamilyInstance, ParameterType
from Autodesk.Revit.UI.Selection import ObjectType

from boostutils import get_parameter
import rpw

from pyrevit import forms

__doc__ = 'Open external resource for selected family instance.'
__title__ = 'Open External Resource'
__author__ = 'Zachary Mathews'

if __name__ == '__main__':
    doc = rpw.doc
    uidoc = rpw.uidoc

    # Get user selection
    selected = [doc.GetElement(id) for id in uidoc.Selection.GetElementIds()]
    if not selected or len(selected) > 1:
        ref = uidoc.Selection.PickObject(
            ObjectType.Element,
            'Please select an element to open its cutsheet'
        )
        el = doc.GetElement(ref)
    else:
        el = selected[0]

    if not type(el) == FamilyInstance:
        sys.exit()

    # Custom item and form item for our select from list form
    class ExternalResource(object):
        def __init__(self, name, url):
            self._name = name
            self._url = url

        @property
        def name(self):
            return self._name

        @property
        def url(self):
            return self._url

    class ExternalResourceItem(forms.TemplateListItem):
        @property
        def name(self):
            return self.item.name + ' : ' + self.item.url

    # Get parameters of type URL that have values
    external_resources = [
        ExternalResource(name=p.Definition.Name, url=p.AsString())
        for p in el.GetOrderedParameters()
        if (
            p.Definition.ParameterType == ParameterType.URL
            and p.HasValue
        )
    ]
    external_resources.extend([
        ExternalResource(name=p.Definition.Name, url=p.AsString())
        for p in el.Symbol.GetOrderedParameters()
        if (
            p.Definition.ParameterType == ParameterType.URL
            and p.HasValue
        )
    ])

    if not external_resources:
        family_type = get_parameter(
            el,
            builtin='ELEM_FAMILY_AND_TYPE_PARAM'
        ).AsValueString()
        forms.alert(
            'No external resource parameters '
            'found for {}.'.format(family_type),
            ok=False,
            cancel=True,
            exitscript=True
        )

    # Allow user to select which external resources to open
    external_resource_items = [
        ExternalResourceItem(ext_res) for ext_res in external_resources
    ]
    res = forms.SelectFromList.show(
        context=external_resource_items,
        multiselect=True,
        height=800,
        width=800
    )

    if res:
        for external_resource in res:
            os.startfile(external_resource.url, 'open')
