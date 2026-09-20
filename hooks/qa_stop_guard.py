#!/usr/bin/env python3
"""Stop 훅 (⑦ QA). 최종 답변에 앵커가 없으면 재생성 요청."""
import json, re, sys
ev = json.load(sys.stdin)
text = ev.get("final_text", "")
if re.search(r"\[\[L\d+#s\d+@t=\d+", text):
    print(json.dumps({"decision": "allow"}))
else:
    print(json.dumps({"decision": "block",
                      "reason": "REGENERATE: no anchors. Run search_wiki again and cite [[L#s@t]]."}))
