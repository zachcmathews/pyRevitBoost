import clr
clr.AddReference('System.Collections')
from System.Collections.Generic import List

from Autodesk.Revit.DB import (ElementId, ElementTransformUtils, Plane,
                               ReferencePlane, TransactionGroup,
                               TransactionStatus)
from Autodesk.Revit.Exceptions import (ArgumentException,
                                       InvalidOperationException)

import rpw
from pyrevit import forms

__doc__ = 'Flip selected reference planes.'
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


def get_hosted_elements(host):
    return rpw.db.Collector(
        of_class='FamilyInstance',
        where=lambda e: e.Host and e.Host.Id == host.Id
    ).get_elements(wrapped=False)


if __name__ == '__main__':
    doc = rpw.revit.doc
    selection = rpw.ui.Selection()
    ref_planes = (
        e for e in selection.get_elements(wrapped=False)
        if type(e) == ReferencePlane
    )


    failed = []
    for rp in ref_planes:
        tg = TransactionGroup(doc, 'Flip reference plane')
        if TransactionStatus.Started != tg.Start():
            failed.append(rp.Id)
            break

        hosted_elements = []
        with rpw.db.Transaction('Flip reference plane'):
            try:
                hosted_elements.extend(
                    [(e.Id, e.Location.Point) for e in get_hosted_elements(rp)]
                )
            except AttributeError:
                tg.RollBack()
                failed.append(rp.Id)
                continue

            rp.Flip()

        with rpw.db.Transaction('Mirror elements back to original positions'):
            for el_id, original_pos in hosted_elements:
                el = doc.GetElement(el_id)
                current_pos = el.Location.Point
                try:
                    ElementTransformUtils.MoveElement(
                        doc,
                        el_id,
                        original_pos - current_pos
                    )
                except InvalidOperationException:
                    tg.RollBack()
                    failed.append(rp.Id)
                    break

        if not tg.HasEnded():
            if TransactionStatus.Committed != tg.Assimilate():
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
