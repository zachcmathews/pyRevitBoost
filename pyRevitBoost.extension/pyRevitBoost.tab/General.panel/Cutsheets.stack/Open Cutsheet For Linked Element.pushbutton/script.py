# pylint: disable=import-error
import sys
import os
from Autodesk.Revit.DB import FamilyInstance, ParameterType
from Autodesk.Revit.UI.Selection import ObjectType
from Autodesk.Revit.Exceptions import OperationCanceledException

from boostutils import get_parameter
import rpw

from pyrevit import forms

__doc__ = 'Open cutsheet for selected family instances in linked document.'
__title__ = 'Open Linked Cutsheet'
__author__ = 'Zachary Mathews'

if __name__ == '__main__':
    doc = rpw.doc
    uidoc = rpw.uidoc
    selection = uidoc.Selection

    try:
        ref = selection.PickObject(ObjectType.LinkedElement,
                                   'Please select a family instance '
                                   'in a linked model.')
    except OperationCanceledException:
        sys.exit()

    ref_in_link = ref.CreateReferenceInLink()

    link_instance = doc.GetElement(ref)
    link_doc = link_instance.GetLinkDocument()
    el = link_doc.GetElement(ref_in_link)

    if type(el) == FamilyInstance:
        family_type = get_parameter(
            el,
            builtin='ELEM_FAMILY_AND_TYPE_PARAM'
        ).AsValueString()

        # Check if cutsheet parameter exists
        cutsheet_param = get_parameter(el, name='Cutsheet')
        if not cutsheet_param:
            forms.alert(
                'No cutsheet parameter found for {}.'.format(family_type),
                ok=False,
                cancel=True,
                exitscript=True
            )

        # Check that cutsheet parameter is of correct type and has a value
        if (
            cutsheet_param.Definition.ParameterType == ParameterType.URL
            and cutsheet_param.HasValue()
        ):
            cutsheet = cutsheet_param.AsString()

            # Check that specified cutsheet is an existing pdf
            if os.path.isfile(cutsheet):
                if os.path.splitext(cutsheet)[1] == 'pdf':
                    os.startfile(cutsheet, 'open')
                else:
                    forms.alert(
                        'The cutsheet specified for {} '
                        'is not a pdf.'.format(family_type),
                        ok=False,
                        cancel=True,
                        exitscript=True
                    )
            else:
                forms.alert(
                    'The cutsheet specified for {} '
                    'does not exist.'.format(family_type),
                    ok=False,
                    cancel=True,
                    exitscript=True
                )
        else:
            forms.alert(
                'No cutsheet specified for {}.'.format(family_type),
                ok=False,
                cancel=True,
                exitscript=True
            )
