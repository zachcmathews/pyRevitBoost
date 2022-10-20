# pylint: disable=import-error
from functools import partial
from pyrevit import forms
import rpw

from common import get_element_meta, Filter, FilterForm

__doc__ = '''\
Filter based on selected criteria.
'''
__author__ = 'Zachary Mathews'
__context__ = 'Selection'

def _get_element_dict(e, meta):
    from Autodesk.Revit.DB import ParameterType, StorageType
    element = {}
    for p in e.Parameters:
        if p.StorageType == StorageType.String:
            if p.HasValue:
                _str = p.AsString()
                _value_str = p.AsValueString()
                element[p.Definition.Name] = (
                    _str if _str is not None else _value_str
                )
            else:
                element[p.Definition.Name] = 'None'

        elif p.StorageType == StorageType.Integer:
            if p.HasValue:
                if p.Definition.ParameterType == ParameterType.YesNo:
                    element[p.Definition.Name] = (
                        'Yes' if p.AsInteger() == 1 else 'No'
                    )
                else:
                    element[p.Definition.Name] = p.AsValueString()
            else:
                element[p.Definition.Name] = 'None'

        elif p.StorageType == StorageType.Double:
            if p.HasValue:
                element[p.Definition.Name] = p.AsValueString()
            else:
                element[p.Definition.Name] = 'None'

    element.update(meta)
    return element


def _get_filterable_parameters(elements):
    parameters = set()
    for e in elements:
        parameters.update(e.keys())

    return parameters


if __name__ == '__main__':
    uidoc = rpw.revit.uidoc
    doc = rpw.revit.doc
    selection = rpw.ui.Selection(uidoc=uidoc)
    _get_element_meta = partial(
        get_element_meta,
        workset_table=doc.GetWorksetTable()
    )

    elements = [
        _get_element_dict(e, meta=_get_element_meta(e))
        for e in selection.get_elements(wrapped=False)
    ]

    parameters = _get_filterable_parameters(elements)
    parameters = forms.SelectFromList.show(
        title='Select filter criteria',
        context=sorted(parameters),
        multiselect=True
    )
    if not parameters:
        import sys
        sys.exit()

    criteria = parameters
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
