# pylint: disable=import-error
from System.ComponentModel import (
    INotifyPropertyChanged,
    PropertyChangedEventArgs
)

import re
from Autodesk.Revit.DB import (
    ExternalResourceLoadStatus,
    KeynoteTable,
    ModelPathUtils
)

import rpw
from pyrevit import forms

__doc__ = 'Renumber Keynotes'
__title__ = 'Renumber Keynotes'
__author__ = 'Zachary Mathews'

key_pattern = r'(?P<category>.*?)(?P<number>-?\d+)'


class Keynote(INotifyPropertyChanged):
    def __init__(self, key, value):
        self._originalKey = key
        self._key = key
        self._value = value
        self._isSelected = False
        self._property_changed_handlers = []

    @property
    def OriginalKey(self):
        return self._originalKey

    @OriginalKey.setter
    def OriginalKey(self, value):
        self._originalKey = value

    @property
    def Key(self):
        return self._key

    @Key.setter
    def Key(self, value):
        self._key = value
        self._raise_property_changed('Key')

    @property
    def Value(self):
        return self._value

    @Value.setter
    def Value(self, value):
        self._value = value

    @property
    def IsSelected(self):
        return self._isSelected

    @IsSelected.setter
    def IsSelected(self, value):
        self._isSelected = value
        self._raise_property_changed('IsSelected')

    def _raise_property_changed(self, property_name):
        args = PropertyChangedEventArgs(property_name)
        for handler in self._property_changed_handlers:
            handler(self, args)

    def add_PropertyChanged(self, handler):
        self._property_changed_handlers.append(handler)

    def remove_PropertyChanged(self, handler):
        self._property_changed_handlers.remove(handler)


class Form(forms.WPFWindow):
    def __init__(self, template, keynotes):
        forms.WPFWindow.__init__(self, template)
        self.DataContext = self
        self._keynotes = keynotes

        self._accept = False

    @property
    def Keynotes(self):
        return self._keynotes

    def Increment(self, sender, *args):
        for kn in self.Keynotes:
            if not kn.IsSelected:
                continue

            match = re.match(key_pattern, kn.Key)
            if not match:
                continue

            category = match.group('category')
            number = int(match.group('number'))

            kn.Key = category + str(number + 1)

    def Decrement(self, sender, *args):
        for kn in self.Keynotes:
            if not kn.IsSelected:
                continue

            match = re.match(key_pattern, kn.Key)
            if not match:
                continue

            category = match.group('category')
            number = int(match.group('number'))

            kn.Key = category + str(number - 1)

    def Accept(self, sender, *args):
        self._accept = True
        self.Close()

    def Cancel(self, sender, *args):
        self.Close()

    def Show(self):
        self.ShowDialog()
        return self._accept


def main():
    doc = rpw.revit.doc
    keynote_table = KeynoteTable.GetKeynoteTable(doc)
    keynotes_path = ModelPathUtils.ConvertModelPathToUserVisiblePath(
        keynote_table.GetExternalFileReference().GetAbsolutePath()
    )

    keynotes = [
        Keynote(kn.Key, kn.KeynoteText)
        for kn in keynote_table.GetKeyBasedTreeEntries()
        if re.match('^' + key_pattern + '$', kn.Key)
    ]

    accept = Form(
        template='form.xaml',
        keynotes=keynotes
    ).Show()

    if not accept:
        return

    updated_lines = []
    with open(keynotes_path, 'r') as f:
        lines = f.read().split('\n')

    for line in lines:
        match = re.match('^(?P<key>' + key_pattern + ').*', line)
        if not match:
            updated_lines.append(line)
            continue

        key = match.group('key')
        keynote = next(kn for kn in keynotes if kn.OriginalKey == key)
        if keynote.Key == keynote.OriginalKey:
            updated_lines.append(line)
            continue

        updated_line = re.sub(keynote.OriginalKey, keynote.Key, line)
        updated_lines.append(updated_line)

    print('\n'.join(updated_lines))

    # with rpw.db.Transaction('Reload keynotes', doc=doc) as t:
    #     result = keynote_table.Reload(None)
    #     if not (
    #         ExternalResourceLoadStatus.Success == result
    #         or ExternalResourceLoadStatus.ResourceAlreadyCurrent == result
    #     ):
    #         forms.alert("Couldn't reload keynotes.")


if __name__ == '__main__':
    main()
