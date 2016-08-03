#!/usr/bin/env python
# -*- coding: utf-8 -*-

# Dayi IME table creator
#
# Read all *.cin file in local dir, assuming they are in good xcin format
# insert them into a SQLite database dayi.db for easier further manipulation

import argparse
import sqlite3
import os

def parse_cmdline():
    parser = argparse.ArgumentParser(description="Dayi input table creator")
    parser.add_argument("-d", dest="db", help="DB to use", default="scratch.db")
    parser.add_argument("-f", dest="freq", help="Frequency table", default="word_freq.txt")
    parser.add_argument("-o", dest="out", help="Output file", default="output.cin")
    parser.add_argument("--osx", dest="osx", default=False, action='store_true',
                        help="Generate in a format for MacOSX. Default is GCIN format.")
    options = parser.parse_args()
    return options

def read_incode_outchar(files):
    "Given a list of files in cin format, output dayi code points from each"
    for f in files:
        with open(f) as fp:
            for l in fp.readlines():
                if l[0] in ['#','%'] or ' ' not in l.strip():
                    continue # skip comment lines or lines doesn't seem like code point
                inout = l.decode('utf8').strip().split(None,1)
                if len(inout) != 2:
                    continue # not in "code output" format
                incode, outchar = inout
                yield incode.upper(), outchar

def populate_db(dbfilename):
    "Read current dir for [0-9]*.cin files, and insert into table `lookup` in SQLite DB"

    # Read from files
    files = [f for f in os.listdir('.') if f.endswith('.cin') and f[0].isdigit()]
    codepoints = read_incode_outchar(files)
    sqlparams  = [c for c in codepoints if len(c[1])==1]
    badcodes   = [c for c in codepoints if len(c[1])!=1]
    if badcodes:
        print "Codes ignored:"
        for code, word in badcodes:
            print "%s = %r (len %d)" % (code, word, len(word))

    # Create and write to DB
    conn = sqlite3.connect(dbfilename)
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS lookup(code COLLATE NOCASE, char COLLATE RTRIM, '
                'PRIMARY KEY(code, char))')
    if sqlparams:
        cur.executemany('INSERT OR IGNORE INTO lookup VALUES (?,?)', sqlparams)
        count = cur.execute('SELECT COUNT(*) FROM lookup').fetchall()[0][0]
        print "Did %d insert from %d files, current table size: %d" % (len(sqlparams), len(files), count)

    # Override some symbols: Remove these symbols from database and replace with new codepoints
    data = filter(None,'''
        =     ，,。,、,！,？,「,」,（,）,『,』,　
        =,    ，,“,”,‘,’,〝,〞,〃
        =,,   《,︽,〈,︿,∩,∪,∫,∮,≦,◢
        =.    。,、,﹕,,．,：,‥,…,‧,∴,∵
        =..   》,︾,〉,﹀,＞,∟,∠,≧,⊥,⊿
        ='    ′
        =''   」
        =;    ；
        =;;   ：
        =[    「,（,『,【,［,〔,｛,〖,〘,〚,╭
        =[[   ﹁,︵,﹃,︻,﹈,︹,︷,╰
        =]    」,）,』,】,］,〕,｝,〗,〙,〛,╯
        =]]   ﹂,︶,﹄,︼,﹇,︺,︸,╮
    '''.strip().decode('utf8').split("\n"))
    code_dict = dict((code,chars.split(",")) for d in data for code,chars in [d.split()])
    symbol_chars = [(c,) for c in set(c for v in code_dict.values() for c in v)]
    symbol_codes = [(k,) for k in code_dict.keys()]
    symbol_defs = [(k,c) for k,cc in code_dict.iteritems() for c in cc]
    cur.executemany('DELETE FROM lookup WHERE char=?', symbol_chars)
    cur.executemany('DELETE FROM lookup WHERE code=?', symbol_codes)
    cur.executemany('INSERT OR IGNORE INTO lookup VALUES (?,?)', symbol_defs)

    # Commit and close
    conn.commit()
    conn.close()

def fillin_dayi234(dbfilename):
    conn = sqlite3.connect(dbfilename)
    cur = conn.cursor()
    sql = """
        -- Find all chars with multiple input codes
        DROP TABLE IF EXISTS dupchars
        ;
        CREATE TABLE dupchars AS
        SELECT char AS char, count(*) AS dupcount, max(length(code)) AS maxcodelen
        FROM lookup GROUP BY char
        ;

        -- Gather all code from dayi table with code of max length
        DROP TABLE IF EXISTS dayi4
        ;
        CREATE TABLE dayi4 AS
        SELECT D.char AS char, D.code AS code
        FROM dupchars C LEFT JOIN lookup D ON C.char=D.char AND LENGTH(D.code)=C.maxcodelen
        ;

        -- Derive dayi3 and dayi2 tables
        DROP TABLE IF EXISTS dayi3
        ;
        CREATE TABLE dayi3 AS
        SELECT char AS char,
               CASE WHEN LENGTH(code)=4 THEN SUBSTR(code,1,2)||SUBSTR(code,4,1) ELSE code END AS code
        FROM dayi4
        ;
        DROP TABLE IF EXISTS dayi2
        ;
        CREATE TABLE dayi2 AS
        SELECT char AS char,
               CASE WHEN LENGTH(code)=3 THEN SUBSTR(code,1,1)||SUBSTR(code,3,1) ELSE code END AS code
        FROM dayi3
        ;
    """
    cur.executescript(sql)
    # The following SQL can print all chars with multiple input codes from dayi4 table
    # sql = """
    #     SELECT D.char AS char, D.code AS code
    #     FROM (SELECT char FROM dayi4 GROUP BY char HAVING COUNT(*)>1) C
    #     LEFT JOIN dayi4 D USING(char)
    # """
    conn.commit()
    conn.close()

def create_wordfreq(dbfilename, wordfreqfile):
    '''
    Read char frequency count from file and sort the IME table by frequency.
    Write result to new table `result`
    '''
    def _read_from_file(f):
        with open(f) as fp:
            # structure of the file:
            # 單字  序號  (部首)  筆劃  頻次  頻率  累積 頻次  累積 頻率  見檔次  見檔率  
            for l in fp.readlines():
                toks = l.decode('utf8').split()
                if len(toks[0]) != 1:
                    continue # probably first line, the header
                yield toks[0], int(toks[3]) # return the char and frequency count

    sqlparams = _read_from_file(wordfreqfile)
    conn = sqlite3.connect(dbfilename)
    cur = conn.cursor()
    cur.execute('CREATE TABLE IF NOT EXISTS wordfreq(char PRIMARY KEY, freq)')
    cur.executemany('INSERT OR IGNORE INTO wordfreq VALUES(?,?)', sqlparams)
    # Non-CJK symbols/punctuations are set to negative freq
    cur.execute('INSERT OR IGNORE INTO wordfreq SELECT char, -1 FROM lookup WHERE char<?', ('\u3000',))
    # Set some symbols in particular order
    symchars = '''
        ， 。 、 ！ ？ 　 “ ” ‘ ’ 〝 〞 〃
        《 》 ︽ ︾ ： ﹕  ． ‧ ； ′
        「 」 （ ） 『 』 【 】 ［ ］ 〔 〕 ｛ ｝ 〈 〉 〖 〗〘〙〚〛
        ﹁ ﹂ ︵ ︶ ﹃ ﹄ ︻ ︼ ﹇ ﹈ ︹ ︺ ︷ ︸ ︿ ﹀
    '''.strip().decode('utf8').split()
    delta = 1.0/(1.0+len(symchars))
    for i,c in enumerate(symchars):
        freq = 1.0 - i*(delta+1)
        cur.execute('INSERT OR REPLACE INTO wordfreq VALUES(?,?)', (c,freq))
    # Create result table
    cur.execute('DROP TABLE IF EXISTS result')
    cur.execute('''
        CREATE TABLE result AS
        SELECT code AS code, char AS char, COALESCE(freq,0) AS freq
        FROM lookup
        LEFT JOIN wordfreq USING(char)
        ORDER BY code ASC, COALESCE(freq,0) DESC''')
    # Write and output
    conn.commit()
    conn.close()

_GCIN_FILE_HEADER = u'''
%gen_inp
%ename Dayi:en;大易:zh;
%cname 大易
%selkey 1234567890
#%encoding utf-8
#%endkey ='
#%dupsel 9
%space_style 1
%keyname begin
,   力
.   點
/   竹
0   金
1   言
2   牛
3   目
4   四
5   王
6   門
7   田
8   米
9   足
;   虫
A   人
B   馬
C   七
D   日
E   一
F   土
G   手
H   鳥
I   木
J   月
K   立
L   女
M   雨
N   魚
O   口
P   耳
Q   石
R   工
S   革
T   糸
U   艸
V   禾
W   山
X   水
Y   火
Z   心
=   符
'   標
`   ～
-   ─
[   ［
]   ］
\   ＼
%keyname end
%chardef begin
'''.strip()

_GCIN_FILE_FOOTER = '''
%chardef end
'''.strip()

_MACOSX_FILE_HEADER = u'''
METHOD: TABLE
ENCODE: TC
PROMPT: 大易
VERSION: 1.0
DELIMITER: ,
MAXINPUTCODE: 4
VALIDINPUTKEY: 0123456789=;,./`-\'[]ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz
TERMINPUTKEY: 123456
BEGINCHARACTER
'''.strip()

_MACOSX_FILE_FOOTER = '''
ENDCHARACTER
'''.strip()

def output_gcin(dbfilename, outputfilename):
    "Generate IME table from `result` in the database and write to outputfilename"
    outputlines = []
    # Read from database
    conn = sqlite3.connect(dbfilename)
    cur = conn.cursor()
    for code, char in cur.execute("SELECT code, char FROM result"):
        outputlines.append("%-6s%s" % (code, char))
    conn.commit()
    conn.close()
    # Write to output
    wordcount = len(outputlines)
    outputlines = [_GCIN_FILE_HEADER] + outputlines + [_GCIN_FILE_FOOTER]
    with open(outputfilename, "w") as fp:
        fp.write("\n".join(outputlines).encode('utf8'))
    print "Wrote %d code points to GCIN file %s" % (wordcount, outputfilename)

def output_macosx(dbfilename, outputfilename):
    "Generate IME table from `result` in the database and write to outputfilename"
    outputtable = []
    # Read from database
    conn = sqlite3.connect(dbfilename)
    cur = conn.cursor()
    for code, char in cur.execute("SELECT code, char FROM result"):
        if outputtable and outputtable[-1][0] == code:
            outputtable[-1][1].append(char)
        else:
            outputtable.append([code, [char]])
    conn.commit()
    conn.close()
    # Write to output
    wordcount = sum(len(cc) for _,cc in outputtable)
    outputlines = [_MACOSX_FILE_HEADER] +\
                  ["%-6s%s" % (code, ",".join(chars)) for code,chars in outputtable] +\
                  [_MACOSX_FILE_FOOTER]
    with open(outputfilename, "w") as fp:
        fp.write("\n".join(outputlines).encode('utf-16-be'))
    print "Wrote %d code points to OSX input table file %s" % (wordcount, outputfilename)

def main():
    options = parse_cmdline()
    populate_db(options.db)
    create_wordfreq(options.db, options.freq)
    if options.osx:
        output_macosx(options.db, options.out)
    else:
        output_gcin(options.db, options.out)

if __name__ == '__main__':
    main()

# vim:set ts=4 sw=4 sts=4 et:
