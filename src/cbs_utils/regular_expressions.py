"""
This modules contains a collection of often used regular expressions
"""

###########################################
# BTW number
###########################################
# examples of the btw code are
# NL001234567B01, so always starting with NL, 9 digits, a B, and then 2 digits
# the problem is that sometime companies add dots in the btw code, such as
# NL8019.96.028.B.01
# the following regular expressions allows to have 0 or 1 dot after each digit
BTW_REGEXP = r"\bNL([\d][\.]{0,1}){9}B[\.]{0,1}([\d][\.]{0,1}){1}\d\b"

###########################################
# KVK number
###########################################
# KVK_REGEXP = r"\b([\d][\.]{0,1}){7}\d\b"  # 8 digits. may contain dots, not at the end
# this regular expression replaces the \b word boundaries of the previous version with the part
# ((?![-\w])|(\s^)), because the word boundary also match a hyphen, which means that -232 also
# is allowed. This give many hits for the kvk which are not kvk numbers but just a part of the
# coding. In order to exclude the hyphen , I have replaced it with the new version
KVK_REGEXP = r"((?![-\w])|(\s|^))([\d][\.]{0,1}){7}\d((?![-\w])|(\s|^))"
# 12345678 -> match
# A-12345678 -> no match
# A12345678 -> no match

############################################
# POSTAL CODE
###########################################
ZIP_REGEXP = r"[1-9]\d{3}\s{0,1}[A-Z]{2}"  # 4 digits in range 1000, 9999, 2 capitals, 0 or 1 space
###########################################


