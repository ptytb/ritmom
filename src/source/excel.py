from os.path import abspath

from win32com.client import Dispatch


class ExcelSource:
    def __init__(self, phrasebook):
        xl = Dispatch("Excel.Application")
        wb = xl.Workbooks.Open(abspath(phrasebook))
        # ws = wb.Sheets('ForAudio')
        xl.Visible = False
        r = xl.Range('C:D')  # col C: foreign, col D: native
        self.table = r.GetValue()
        wb.Close()
        xl.Quit()

    def __iter__(self):
        return self

    def __next__(self):
        """Generator. Scans Excel columns until two empty lines reached."""
        i = 0
        gap = 0
        while True:
            word = self.table[i][0]

            if word is None:
                gap += 1
                if gap == 15:
                    return
            else:
                gap = 0
                yield self.table[i]

            i += 1



