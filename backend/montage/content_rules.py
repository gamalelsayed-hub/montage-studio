"""قواعد المحتوى للقطات (متفق عليها مع صاحب المشروع):

الوشوش عادي تظهر، بس أي ست في اللقطة لازم تكون محجبة ولابسة لبس شرعي محتشم.
بنطبّق ده على كلمات البحث (Pexels) وعلى أي وصف بيتبعت لتوليد صور بعدين.
البحث مايضمنش النتيجة 100%، فالواجهة بتعرض بدائل والمراجعة النهائية بالعين.
"""

from __future__ import annotations

import re

_FEMALE = re.compile(r"\b(woman|women|girl|girls|lady|ladies|mother|mom|wife|female|"
                     r"daughter|sister|grandmother|bride|she|her)\b", re.I)
_GROUP = re.compile(r"\b(people|person|persons|crowd|family|families|couple|customers?|"
                    r"shoppers?|students?|audience|friends|group|team|employees|workers)\b", re.I)
_ALREADY = re.compile(r"\b(hijab|hijabi|niqab|muslim|modest)\b", re.I)

# بيتبعت مع أي طلب توليد صورة أو ترجمة وصف لكلمات بحث
PROMPT_RULE = (
    "Content rule: showing faces is fine. Any woman or girl who appears must wear a hijab "
    "and modest, loose Islamic clothing covering arms and legs. Never suggest revealing "
    "clothing. For scenes with women, include the word 'hijab' in the search query."
)


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
