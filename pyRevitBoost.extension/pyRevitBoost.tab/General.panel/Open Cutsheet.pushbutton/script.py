# pylint: disable=import-error
import os
from Autodesk.Revit.DB import FamilyInstance
from Autodesk.Revit.UI.Selection import ObjectType

from boostutils import get_parameter
import rpw

from pyrevit import forms

__doc__ = 'Open cutsheet for selected family instances.'
__title__ = 'Open\nCutsheet'
__author__ = 'Zachary Mathews'

if __name__ == '__main__':
    doc = rpw.doc
    uidoc = rpw.uidoc
    selection = uidoc.Selection

    ref = selection.PickObject(ObjectType.LinkedElement,
                               'Please select a family instance ' +
                               'in a linked model.')
    ref_in_link = ref.CreateReferenceInLink()

    link_instance = doc.GetElement(ref)
    link_doc = link_instance.GetLinkDocument()
    el = link_doc.GetElement(ref_in_link)

    if type(el) == FamilyInstance:
        family_type = get_parameter(
            el,
            builtin='ELEM_FAMILY_AND_TYPE_PARAM'
        ).AsValueString()

        cutsheet_param = get_parameter(el, name='Cutsheet')
        if not cutsheet_param:
            forms.alert(
                'No cutsheet parameter found for {}.'.format(family_type),
                ok=False,
                cancel=True,
                exitscript=True
            )

        cutsheet = cutsheet_param.AsString()
        if cutsheet:
            os.startfile(cutsheet, 'open')
        else:
            forms.alert(
                'No cutsheet specified for {}.'.format(family_type),
                ok=False,
                cancel=True,
                exitscript=True
            )
