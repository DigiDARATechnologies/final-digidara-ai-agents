"""Measure one real answer-submit and next-question transition."""
import argparse
import json
import time
from urllib.request import Request, urlopen


def call(url,method="GET",body=None,token=None):
    headers={"Content-Type":"application/json"}
    if token:headers["Authorization"]=f"Bearer {token}"
    request=Request(url,method=method,headers=headers,data=json.dumps(body).encode() if body is not None else None)
    started=time.perf_counter()
    with urlopen(request,timeout=30) as response:payload=json.load(response)
    return payload,(time.perf_counter()-started)*1000


def main():
    parser=argparse.ArgumentParser();parser.add_argument("test_id");parser.add_argument("--base-url",default="http://127.0.0.1:5000/api/aptitude");parser.add_argument("--token");parser.add_argument("--answer",choices=list("ABCD"),default="A");args=parser.parse_args()
    _,answer_ms=call(f"{args.base_url}/tests/{args.test_id}/answer","POST",{"selected_answer":args.answer},args.token)
    deadline=time.monotonic()+15;next_ms=0;status="preparing"
    while status=="preparing" and time.monotonic()<deadline:
        payload,duration=call(f"{args.base_url}/tests/{args.test_id}/resume",token=args.token);next_ms+=duration;status=payload.get("status")
        if status=="preparing":time.sleep(float(payload.get("retry_after_ms",500))/1000)
    print(json.dumps({"answer_submit_ms":round(answer_ms,2),"next_question_network_ms":round(next_ms,2),"next_status":status},indent=2))


if __name__=="__main__":main()
