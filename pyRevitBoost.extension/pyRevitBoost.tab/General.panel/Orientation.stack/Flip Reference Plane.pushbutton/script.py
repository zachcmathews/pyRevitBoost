from Autodesk.Revit.DB import ReferencePlane

import rpw
from pyrevit import forms

__doc__ = 'Flip selected reference planes.'
__author__ = 'Zachary Mathews'
__context__ = 'Selection'

if __name__ == '__main__':
    selection = rpw.ui.Selection()
    ref_planes = (
        e for e in selection.get_elements(wrapped=False)
        if type(e) == ReferencePlane
    )


    failed = []
    with rpw.db.Transaction('Flip reference planes'):
        for rp in ref_planes:
            try:
                rp.Flip()
            except:
                failed.append(rp.Id)

    if failed:
        selection.clear()
        selection.add(failed)
        selection.update()
        forms.alert(
            title='Failed to flip reference plane',
            msg=('Failed to flip {} selected elements.'
                 .format(len(failed))),
            exitscript=True
        )
