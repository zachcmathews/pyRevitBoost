# pylint: disable=import-error
from functools import partial
import rpw

from common import get_element_meta, Filter, FilterForm

__doc__ = '''\
Filter based on category, family, type and workset.
'''
__author__ = 'Zachary Mathews'
__context__ = 'Selection'

if __name__ == '__main__':
    uidoc = rpw.revit.uidoc
    doc = rpw.revit.doc
    selection = rpw.ui.Selection(uidoc=uidoc)
    _get_element_meta = partial(
        get_element_meta,
        workset_table=doc.GetWorksetTable()
    )

    elements = [
        _get_element_meta(e)
        for e in selection.get_elements(wrapped=False)
        if _get_element_meta(e)
    ]

    criteria = [
        'Category', 'Family', 'Type', 'Workset', 'Phase Created',
        'Phase Demolished'
    ]
    if elements:
        _filter = Filter(criteria, elements)

        # Show form
        filtered_elements = FilterForm(
            template='../FilterForm.xaml',
            _filter=_filter,
            elements=elements
        ).show_dialog()

        # Update selection
        selection.clear()
        selection.add([e['ID'] for e in filtered_elements])
        selection.update()
