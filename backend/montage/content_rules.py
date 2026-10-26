"""قواعد المحتوى للقطات (متفق عليها مع صاحب المشروع):

الوشوش عادي تظهر، بس أي ست في اللقطة لازم تكون محجبة ولابسة لبس شرعي محتشم.
بنطبّق ده على كلمات البحث (Pixabay / Pexels) وعلى أي وصف بيتبعت لتوليد صور بعدين.
البحث مايضمنش النتيجة 100%، فالواجهة بتعرض بدائل والمراجعة النهائية بالعين.
"""

from __future__ import annotations

import re

_FEMALE = re.compile(r"\b(woman|women|girl|girls|lady|ladies|mother|mom|wife|female|"
                     r"daughter|sister|grandmother|bride|she|her)\b", re.I)
_GROUP = re.compile(r"\b(people|person|persons|crowd|family|families|couple|customers?|"
                    r"shoppers?|students?|audience|friends|group|team|employees|workers)\b", re.I)
_ALREADY = re.compile(r"\b(hijab|hijabi|niqab|muslim|modest)\b", re.I)
# لقطات مش مناسبة لفيديو ديني توعوي (أعياد ورموز أديان تانية، خمور، لبس عريان...).
# بنشيلها من النتايج بالـ tags اللي الموقع بيرجّعها.
_BANNED = re.compile(r"\b(christmas|xmas|santa|advent|church|cathedral|chapel|crucifix|jesus|christ|"
                     r"easter|halloween|buddha|buddhist|hindu|wine|beer|alcohol|whisky|whiskey|vodka|"
                     r"cocktail|champagne|pub|casino|gambling|bikini|swimsuit|swimwear|lingerie|"
                     r"underwear|sexy|pig|pork|bacon|tattoo)s?\b", re.I)

# بيتبعت مع أي طلب توليد صورة أو ترجمة وصف لكلمات بحث
PROMPT_RULE = (
    "Content rule: showing faces is fine. Any woman or girl who appears must wear a hijab "
    "and modest, loose Islamic clothing covering arms and legs. Never suggest revealing "
    "clothing. For scenes with women, include the word 'hijab' in the search query. "
    "Avoid anything unsuitable for an Islamic awareness video: Christmas or other religious "
    "holidays and symbols, churches, alcohol, gambling, pork."
)


def is_allowed(text: str | None) -> bool:
    """النتيجة (من الـ tags أو الوصف بتاعها) مافيهاش حاجة من الممنوعات؟"""
    return not _BANNED.search(text or "")


def apply_to_query(query: str) -> str:
    """يزوّد كلمات البحث اللي بتقرّب النتايج من القاعدة."""
    query = " ".join(query.split())
    if not query or _ALREADY.search(query):
        return query
    if _FEMALE.search(query):
        return f"{query} hijab"
    if _GROUP.search(query):
        return f"{query} muslim hijab"
    return query
