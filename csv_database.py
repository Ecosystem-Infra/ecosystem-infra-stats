import csv
from collections import OrderedDict


class CSVIndexedDB(object):
    """A simple database backed by CSV and indexed by the first column."""

    def __init__(self, csv_path, fields=None):
        """Constructs a CSVIndexedDB.

        Args:
            csv_path: The path to a CSV file.
            fields: A list of fields.
        """
        assert len(list(fields)) > 1
        self.csv_path = csv_path
        self.fields = fields or []
        self.entry_by_id = OrderedDict()

    @property
    def id_field(self):
        return self.fields[0]

    def read(self):
        with open(self.csv_path, 'r') as f:
            # Omit fieldnames to use the first row as the header.
            reader = csv.DictReader(f)
            if self.fields:
                assert self.fields == reader.fieldnames
            else:
                self.fields = reader.fieldnames
            for row in reader:
                self.add(row)

    def write(self, order=None):
        """Writes the DB to the CSV file.

        Args:
            order: 'asc', 'desc', or None (do not sort).
        """
        with open(self.csv_path, 'w') as f:
            writer = csv.DictWriter(f, fieldnames=self.fields)
            writer.writeheader()
            if order == 'asc':
                for key in sorted(self.entry_by_id.keys()):
                    writer.writerow(self.entry_by_id[key])
            elif order == 'desc':
                for key in sorted(self.entry_by_id.keys(), reverse=True):
                    writer.writerow(self.entry_by_id[key])
            else:
                for key in self.entry_by_id:
                    writer.writerow(self.entry_by_id[key])

    def add(self, row):
        assert row[self.id_field] not in self.entry_by_id
        assert len(row) == len(self.fields)
        assert all(field in self.fields for field in row)
        self.entry_by_id[row[self.id_field]] = row

    def delete(self, id_to_delete):
        # Everything in csv is a string.
        id_to_delete = str(id_to_delete)
        assert id_to_delete in self.entry_by_id
        del self.entry_by_id[id_to_delete]

    def get(self, id_to_get):
        # Everything in csv is a string.
        id_to_get = str(id_to_get)
        if id_to_get not in self.entry_by_id:
            return None
        return self.entry_by_id[id_to_get]

    def __len__(self):
        return len(self.entry_by_id)

    def __iter__(self):
        return self.entry_by_id.iterkeys()

    def keys(self):
        return self.entry_by_id.keys()

    def values(self):
        return self.entry_by_id.values()


class CommitDB(CSVIndexedDB):
    def __init__(self, csv_path):
        super(CommitDB, self).__init__(csv_path, fields=[
            'Month', 'Total commits', 'Chromium exports', 'Gecko exports',
            'Servo exports', 'WebKit exports'])


class ChromiumWPTUsageDB(CSVIndexedDB):
    def __init__(self, csv_path):
        super(ChromiumWPTUsageDB, self).__init__(csv_path, fields=[
            'date', 'total_changes', 'changes_with_wpt', 'fraction'])
