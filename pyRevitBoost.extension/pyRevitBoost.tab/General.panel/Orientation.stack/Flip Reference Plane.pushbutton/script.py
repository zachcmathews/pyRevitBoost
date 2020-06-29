# pylint: disable=import-error
import sys
from Autodesk.Revit.DB import (ElementTransformUtils, ReferencePlane,
                               TransactionGroup, TransactionStatus)
from Autodesk.Revit.Exceptions import InvalidOperationException

import rpw
from pyrevit import forms

__doc__ = 'Flip selected reference plane.'
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
    ref_planes = [
        e for e in selection.get_elements(wrapped=False)
        if type(e) == ReferencePlane
    ]

    if len(ref_planes) > 1:
        selected_name = forms.SelectFromList.show(
            title='Select reference plane.',
            context=[rp.Name for rp in ref_planes]
        )
        if not selected_name:
            sys.exit()
        else:
            [rp] = [rp for rp in ref_planes if rp.Name == selected_name]
    else:
        rp = ref_planes[0]

    failed = []
    tg = TransactionGroup(doc, 'Flip reference plane')
    if TransactionStatus.Started != tg.Start():
        failed.append(rp.Id)
    else:
        hosted_elements = []
        try:
            hosted_elements.extend(
                [(e.Id, e.Location.Point) for e in get_hosted_elements(rp)]
            )
        except AttributeError:
            tg.RollBack()
            failed.append(rp.Id)
        else:
            if hosted_elements:
                cont = forms.alert(
                    title='Flip Reference Plane',
                    msg='{} hosted elements will be affected. Continue?'
                        .format(len(hosted_elements)),
                    ok=False,
                    yes=True,
                    no=True
                )
                if not cont:
                    tg.RollBack()
                    sys.exit()

        with rpw.db.Transaction('Flip reference plane'):
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
