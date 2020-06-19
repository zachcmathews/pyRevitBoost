from Autodesk.Revit.DB import HostObject, ReferencePlane

import rpw
from pyrevit import forms

__doc__ = 'Match normal of work plane (i.e. reference plane, ceiling, etc).'
__author__ = 'Zachary Mathews'
__context__ = 'Selection'


def get_hosted_elements(host):
    return rpw.db.Collector(
        of_class='FamilyInstance',
        where=lambda e: e.Host and e.Host.Id == host.Id
    ).get_elements(wrapped=False)


def get_host_elements(elements):
    host_elements = []
    for el in elements:
        if isinstance(el, HostObject) or type(el) == ReferencePlane:
            host_elements.append(el)

    return host_elements


if __name__ == '__main__':
    doc = rpw.doc

    selection = rpw.ui.Selection()
    selected = [e for e in selection.get_elements(wrapped=False)]
    host_elements = get_host_elements(selected)

    flip_all_hosted = False
    if host_elements:
        flip_all_hosted = forms.alert(
            title='Flip all hosted elements?',
            msg='You have selected {} hosting element(s). '
                'Would you like to flip all hosted elements to match the '
                'host object\'s normal?'
                .format(len(host_elements)),
            ok=False,
            yes=True,
            no=True
        )

    elements = [
        e for e in selected
        if e not in host_elements
    ]
    if flip_all_hosted:
        for host in host_elements:
            elements.extend(get_hosted_elements(host=host))

    failed = []
    with rpw.db.Transaction('Match work plane normal'):
        for el in elements:
            try:
                el.IsWorkPlaneFlipped = False
            except:
                failed.append(el.Id)

    if failed:
        selection.clear()
        selection.add(failed)
        selection.update()
        forms.alert(
            title='Failed to match work plane normal',
            msg=('Failed to match work plane normal for '
                 '{} selected element(s).'
                 .format(len(failed))),
            exitscript=True
        )
