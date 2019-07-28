# 大易輸入法表格

Read in all variations of dayi input method mapping table and create a SQLite
database. Then a normalized input table is created.

```
$ creator.py --help
usage: creator.py [-h] [-d DB] [-f FREQ] [-o OUT] [--osx]

Dayi input table creator

optional arguments:
  -h, --help  show this help message and exit
  -d DB       DB to use
  -f FREQ     Frequency table
  -o OUT      Output file
  --osx       Generate in a format for MacOSX. Default is GCIN format.
```
