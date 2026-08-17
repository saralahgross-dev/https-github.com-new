from storage import add_source, add_style_examples, list_sources

CURATED = {
'midterm sample': [
 {'section':'על מי / על מה נאמר','prompt':'שמוציאם ומכניסם במספר','perek':1,'difficulty':4},
 {'section':'על מי / על מה נאמר','prompt':'ותמלא הארץ אותם','perek':1,'difficulty':4},
 {'section':'על מי / על מה נאמר','prompt':'עשה עצמו כאלו לא ידעו','perek':1,'difficulty':5},
 {'section':'על מי / על מה נאמר','prompt':'ויקח את בת לוי','perek':2,'difficulty':4},
 {'section':'על מי / על מה נאמר','prompt':'ותלך העלמה','perek':2,'difficulty':4},
 {'section':'על מי / על מה נאמר','prompt':'בער באש','perek':3,'difficulty':4},
 {'section':'על מי / על מה נאמר','prompt':'אשר אתה עומד עליו','perek':3,'difficulty':4},
 {'section':'בקשר למה למדנו','prompt':'״שרגא בטהרא״ — הסבירי בקיצור ובקשר למה למדנו.','perek':2,'difficulty':6},
 {'section':'בקשר למה למדנו','prompt':'״בשכר נשים״ — בקשר למה למדנו?','perek':1,'difficulty':5},
 {'section':'בקשר למה למדנו','prompt':'״עמו אנכי בצרה״ — בקשר למה למדנו?','perek':3,'difficulty':5},
 {'section':'שאלת ותשובת רש״י','prompt':'מהי שאלת רש״י ותשובתו על ״אהיה אשר אהיה״?','perek':3,'difficulty':6},
 {'section':'שאלת ותשובת רש״י','prompt':'מהי שאלת רש״י ותשובתו על ״זה שמי לעלם״?','perek':3,'difficulty':6},
 {'section':'שאלות קצרות','prompt':'למה בני ישראל נמשלו לסנה?','perek':3,'difficulty':5},
 {'section':'שאלות קצרות','prompt':'לפי הרמב״ן, למה אמר ה׳ ״ושמעו לקולך״ — למה זה בטוח?','perek':3,'difficulty':7},
 {'section':'שאלות קצרות','prompt':'לפי הרמב״ן, למה הראה ה׳ למשה את הסימן הראשון והשני?','perek':4,'difficulty':7},
 {'section':'מפרשים','prompt':'לפי הקדמת הרמב״ן לספר שמות, מתי נחשבו בני ישראל גאולים?','perek':1,'difficulty':7},
 {'section':'מפרשים','prompt':'לפי דעת זקנים על פרק ד׳ פסוקים י׳–י״א, למה משה רבינו פחד ללכת לפרעה?','perek':4,'difficulty':7},
],
'perek gimmel sample': [
 {'section':'על מי / על מה נאמר','prompt':'כי אלך אל פרעה','perek':3,'difficulty':4},
 {'section':'על מי / על מה נאמר','prompt':'כי אהיה עמך','perek':3,'difficulty':4},
 {'section':'על מי / על מה נאמר','prompt':'וזה לך האות','perek':3,'difficulty':5},
 {'section':'שאלות קצרות','prompt':'מהי החיזוק למשה רבינו שהסנה ״איננו אוכל״?','perek':3,'difficulty':5},
 {'section':'שאלות קצרות','prompt':'מדוע אי אפשר להסביר את ״זקני ישראל״ כזקנים סתם?','perek':3,'difficulty':6},
 {'section':'שאלות קצרות','prompt':'מהי שאלת הרמב״ן על ״ושמעו לקולך״ ומהי תשובתו?','perek':3,'difficulty':7},
],
'chapter one quiz sample': [
 {'section':'שאלות קצרות','prompt':'In which ספר was the גלות decreed by ה׳ to the אבות?','perek':1,'difficulty':4},
 {'section':'שאלות קצרות','prompt':'Why are בנ״י still considered exiled once they left מצרים?','perek':1,'difficulty':6},
 {'section':'מפרשים','prompt':'According to Reb Yaakov Kamenetzky, why are בנ״י compared to stars at the beginning of the גלות?','perek':1,'difficulty':6},
 {'section':'שאלת ותשובת רש״י','prompt':'What is רש״י’s question on ״ויוסף היה במצרים״?','perek':1,'difficulty':5},
],
}

def main():
    if any(s['name']=='__seed_marker_v2__' for s in list_sources()): return
    for name,examples in CURATED.items():
        sid=add_source(name,'prior_test')
        add_style_examples(sid,examples)
    add_source('__seed_marker_v2__','system')
main()
