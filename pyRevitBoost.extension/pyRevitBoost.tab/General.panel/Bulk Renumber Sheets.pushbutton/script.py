# pylint: disable=import-error
from Autodesk.Revit.DB import BuiltInParameter

import sys
import rpw
from pyrevit import forms

__doc__ = '''\
Bulk renumber sheets.
'''
__title__ = 'Bulk Renumber Sheets'
__author__ = 'Zachary Mathews'


class SheetItem(forms.TemplateListItem):
    @property
    def name(self):
        return '{} - {}'.format(self.item.SheetNumber, self.item.Name)
        

if __name__ == '__main__':
    doc = rpw.revit.doc

    sheets = sorted(
        [SheetItem(s) for s in rpw.db.Collector(
            doc=doc,
            of_class='ViewSheet'
        ).get_elements(wrapped=False)],
        key=lambda s: s.name
    )

    selected_sheets = forms.SelectFromList.show(
        sheets,
        title='Select sheets',
        button_name='Rename Sheets',
        multiselect=True,
    )

    if not selected_sheets:
        sys.exit()

    selected_option = forms.CommandSwitchWindow.show(
        ['Prepend', 'Append']
    )

    if not selected_option:
        sys.exit()

    text = forms.ask_for_string(
        default='',
        prompt='{} text: '.format(selected_option)
    )

    if not text:
        sys.exit()

    with rpw.db.Transaction('Bulk Rename Sheets', doc=doc):
        for sheet in selected_sheets:
            sheet_number_param = sheet.get_Parameter(getattr(BuiltInParameter, 'SHEET_NUMBER'))

            if selected_option == 'Prepend':
                sheet_number_param.Set(text + sheet.SheetNumber)

            elif selected_option == 'Append':
                sheet_number_param.Set(sheet.SheetNumber + text)
    