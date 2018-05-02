from os.path import abspath
import csv


class CsvSource:
    def __init__(self, source):
        self.source = abspath(source)

    def __iter__(self):
        return self

    def __next__(self):
        with open(self.source, newline='', errors='replace', encoding='utf-8') as f:
            csvreader = csv.reader(f)
            for row in csvreader:
                yield row

