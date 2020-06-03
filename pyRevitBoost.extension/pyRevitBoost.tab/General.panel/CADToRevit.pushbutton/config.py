import sys
from pyrevit import forms, script

def edit_config(filepath):
    import os
    os.startfile(filepath)


def draw_block_origins():
    from Autodesk.Revit.DB import XYZ

    import rpw
    from boostutils import draw_circle
    from gather import get_blocks, get_cad_imports

    doc = rpw.revit.doc
    uidoc = rpw.revit.uidoc
    view = uidoc.ActiveView
    level = view.GenLevel

    cad_imports = get_cad_imports()
    if not cad_imports:
        forms.alert(
            title='No CAD import',
            msg='You must have a CAD import to use this command.'
        )
        sys.exit()

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


if __name__ == '__main__':
    cmd = forms.CommandSwitchWindow.show(
        context=['Edit Configuration', 'Draw Block Origins']
    )

    if cmd == 'Edit Configuration':
        script_config = script.get_config(
            section='pyRevitBoost.General.CADToRevit'
        )
        if hasattr(script_config, 'config_file'):
            edit_config(script_config.config_file)
        else:
            forms.alert(
                title='Error',
                msg='No configuration file found.'
            )
    elif cmd == 'Draw Block Origins':
        draw_block_origins()
