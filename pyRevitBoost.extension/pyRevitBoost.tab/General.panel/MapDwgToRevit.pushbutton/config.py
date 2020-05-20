import sys

from Autodesk.Revit.DB import XYZ

import rpw
from pyrevit import forms

from boostutils import draw_circle
from gather import get_blocks, get_cad_imports

doc = rpw.revit.doc
uidoc = rpw.revit.uidoc
view = uidoc.ActiveView
level = view.GenLevel

cad_imports = get_cad_imports()

# Select DWG import if more than one
if len(cad_imports) > 1:
    cad_import = forms.SelectFromList.show(
        title='Select CAD Import to Map to Revit',
        context=cad_imports,
        name_attr='Name'
    )
else:
    [cad_import] = cad_imports

if not cad_import:
    forms.alert(
        title='You must have a CAD import to use this command.',
        msg='{}\n\n{}'.format(config_warning, results)
    )
    sys.exit()

import_transform = cad_import.GetTotalTransform()
blocks = get_blocks(cad_import)

with rpw.db.Transaction('Draw locations'):
    for b in blocks:
        draw_circle(
          center=import_transform.Multiply(b.Transform).OfPoint(XYZ.Zero),
          radius=0.25,
          view=view,
          doc=doc
        )
