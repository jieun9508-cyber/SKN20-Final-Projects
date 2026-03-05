"""
bug_problem_generator.py — BugBubble 문제 동적 생성 서비스

openai 직접 호출 → JSON 파싱 → 검증 → 반환
사용처: socket_server.py > bubble_start 이벤트
"""

import json
import os
import random
import logging
from typing import List, Dict, Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

_client: AsyncOpenAI = None

def _get_client() -> AsyncOpenAI:
    global _client
    if _client is None:
        _client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    return _client


PROMPT_TEMPLATE = """당신은 AI 부트캠프의 실무 디버깅 문제 출제자입니다.
주니어 AI 개발자가 실무에서 맞닥뜨리는 버그 상황을 {count}개 만들어주세요.

## 난이도
{difficulty_desc}

## 카테고리 (골고루 섞어서)
- Python 기초: TypeError, IndexError, KeyError 등
- 데이터 분석: pandas, numpy 관련 에러
- 모델 학습: PyTorch/sklearn shape 불일치, NaN 등
- API/서버: Django, FastAPI 엔드포인트, JSON 파싱 에러
- 배포/환경: import 실패, 경로, 환경변수 누락

## 출력 형식 (JSON 배열, 마크다운 없이 순수 JSON만)
[
  {{
    "title": "한줄 제목 (한국어)",
    "bug_type_name": "에러이름 (예: TypeError)",
    "file_name": "파일명.py",
    "bug_line": 버그줄번호(정수),
    "buggy_code": "버그 포함 코드 (5~10줄, \\n으로 줄구분)",
    "error_log": "에러 로그 (File, Line 포함)",
    "hint": "디버깅 힌트 (1문장)",
    "choices": [
      {{"label": "수정 코드 한 줄", "correct": true}},
      {{"label": "그럴듯한 오답", "correct": false}},
      {{"label": "그럴듯한 오답", "correct": false}},
      {{"label": "그럴듯한 오답", "correct": false}}
    ]
  }}
]

## 규칙
1. choices 정확히 4개, correct=true 반드시 1개만
2. 오답은 그럴듯하지만 다른 에러를 유발하거나 해결 못하는 코드
3. buggy_code는 실제로 해당 에러가 발생하는 코드
4. 시나리오가 "주니어 AI 개발자 업무" 느낌
5. 같은 에러 타입 반복 금지"""

DIFFICULTY_DESC = {
    1: "기초 — Python 문법, 타입 에러 (부트캠프 1개월차)",
    2: "중급 — 라이브러리 에러, 데이터 처리 (부트캠프 3개월차)",
    3: "실무 — 모델 학습, API 연동, 배포 (실무 투입 직전)",
}

FALLBACK_PROBLEMS = [
    {
        "title": "서버 응답 점수 합산 에러", "bug_type_name": "TypeError",
        "file_name": "score_api.py", "bug_line": 4,
        "buggy_code": 'import json\nresponse = \'{"score": "100", "bonus": 50}\'\ndata = json.loads(response)\ntotal = data["score"] + data["bonus"]\nprint(total)',
        "error_log": 'TypeError: can only concatenate str (not "int") to str\nFile "score_api.py", line 4',
        "hint": "JSON에서 파싱한 score의 타입을 확인해보세요.",
        "choices": [
            {"label": 'total = int(data["score"]) + data["bonus"]', "correct": True},
            {"label": 'total = data["score"] + str(data["bonus"])', "correct": False},
            {"label": 'total = str(data["score"] + data["bonus"])', "correct": False},
            {"label": 'total = data["score"].add(data["bonus"])', "correct": False},
        ],
    },
    {
        "title": "리스트 마지막 원소 접근 실패", "bug_type_name": "IndexError",
        "file_name": "data_loader.py", "bug_line": 2,
        "buggy_code": 'batch = ["img1.png", "img2.png", "img3.png"]\nlast = batch[3]\nprint(f"마지막 배치: {last}")',
        "error_log": 'IndexError: list index out of range\nFile "data_loader.py", line 2',
        "hint": "리스트 인덱스는 0부터 시작합니다.",
        "choices": [
            {"label": "last = batch[2]", "correct": True},
            {"label": "last = batch[4]", "correct": False},
            {"label": "last = batch.last()", "correct": False},
            {"label": "last = batch[-0]", "correct": False},
        ],
    },
    {
        "title": "딕셔너리 키 누락 처리", "bug_type_name": "KeyError",
        "file_name": "config.py", "bug_line": 3,
        "buggy_code": 'config = {"host": "localhost", "port": 8080}\nhost = config["host"]\ndb = config["database"]',
        "error_log": "KeyError: 'database'\nFile \"config.py\", line 3",
        "hint": "존재하지 않는 키에 안전하게 접근하는 방법은?",
        "choices": [
            {"label": 'db = config.get("database", "default_db")', "correct": True},
            {"label": 'db = config["db"]', "correct": False},
            {"label": "db = config.database", "correct": False},
            {"label": 'db = config or "default_db"', "correct": False},
        ],
    },
    {
        "title": "None 반환값 속성 접근", "bug_type_name": "AttributeError",
        "file_name": "user_service.py", "bug_line": 7,
        "buggy_code": 'def find_user(users, name):\n    for u in users:\n        if u["name"] == name:\n            return u\n\nresult = find_user([], "Alice")\nprint(result["email"])',
        "error_log": "TypeError: 'NoneType' object is not subscriptable\nFile \"user_service.py\", line 7",
        "hint": "함수가 아무것도 못 찾으면 무엇을 반환하나요?",
        "choices": [
            {"label": 'if result: print(result["email"])', "correct": True},
            {"label": "print(result.email)", "correct": False},
            {"label": 'print(str(result["email"]))', "correct": False},
            {"label": "result = find_user([], 'Alice') or []", "correct": False},
        ],
    },
    {
        "title": "무한 루프 탈출 실패", "bug_type_name": "LogicError",
        "file_name": "trainer.py", "bug_line": 4,
        "buggy_code": 'epoch = 0\nmax_epochs = 5\nwhile epoch < max_epochs:\n    print(f"Epoch {epoch}")\n    epoch = epoch',
        "error_log": "Program hangs (infinite loop)\nLine 5: epoch never increments",
        "hint": "epoch 값이 루프 안에서 변하고 있나요?",
        "choices": [
            {"label": "epoch = epoch + 1", "correct": True},
            {"label": "epoch = epoch - 1", "correct": False},
            {"label": "epoch == epoch + 1", "correct": False},
            {"label": "break", "correct": False},
        ],
    },
    {
        "title": "pandas 컬럼 대소문자 불일치", "bug_type_name": "KeyError",
        "file_name": "preprocess.py", "bug_line": 4,
        "buggy_code": 'import pandas as pd\ndf = pd.read_csv("data.csv")\n# 컬럼명: Age, Name, Score\nprint(df["age"].mean())',
        "error_log": "KeyError: 'age'\nFile \"preprocess.py\", line 4",
        "hint": "CSV 컬럼명의 대소문자를 확인해보세요.",
        "choices": [
            {"label": 'print(df["Age"].mean())', "correct": True},
            {"label": 'print(df.age.mean())', "correct": False},
            {"label": 'print(df[["age"]].mean())', "correct": False},
            {"label": 'print(df.get("age").mean())', "correct": False},
        ],
    },
    {
        "title": "numpy shape 불일치 행렬곱", "bug_type_name": "ValueError",
        "file_name": "model_layer.py", "bug_line": 4,
        "buggy_code": 'import numpy as np\nA = np.ones((3, 4))\nB = np.ones((3, 5))\nresult = np.dot(A, B)\nprint(result.shape)',
        "error_log": "ValueError: shapes (3,4) and (3,5) not aligned\nFile \"model_layer.py\", line 4",
        "hint": "행렬곱에서 앞 행렬의 열 수와 뒤 행렬의 행 수가 일치해야 합니다.",
        "choices": [
            {"label": "B = np.ones((4, 5))", "correct": True},
            {"label": "B = np.ones((3, 4))", "correct": False},
            {"label": "result = np.dot(A, B.T)", "correct": False},
            {"label": "result = A * B", "correct": False},
        ],
    },
    {
        "title": "문자열 포맷 타입 에러", "bug_type_name": "TypeError",
        "file_name": "report.py", "bug_line": 3,
        "buggy_code": 'accuracy = 0.9234\nepochs = 10\nprint("Accuracy: " + accuracy + " after " + epochs + " epochs")',
        "error_log": 'TypeError: can only concatenate str (not "float") to str\nFile "report.py", line 3',
        "hint": "숫자를 문자열과 합치려면 변환이 필요합니다.",
        "choices": [
            {"label": 'print(f"Accuracy: {accuracy} after {epochs} epochs")', "correct": True},
            {"label": 'print("Accuracy: ", accuracy, " after ", epochs)', "correct": False},
            {"label": 'print("Accuracy: " + str(accuracy + epochs))', "correct": False},
            {"label": 'print("Accuracy: " + accuracy)', "correct": False},
        ],
    },
    {
        "title": "환경변수 누락으로 API 키 없음", "bug_type_name": "TypeError",
        "file_name": "openai_client.py", "bug_line": 4,
        "buggy_code": 'import os\nfrom openai import OpenAI\napi_key = os.getenv("OPENAI_API_KEY")\nclient = OpenAI(api_key=api_key)\nresponse = client.chat.completions.create(model="gpt-4o")',
        "error_log": "openai.AuthenticationError: No API key provided\nFile \"openai_client.py\", line 4",
        "hint": "getenv는 키가 없으면 None을 반환합니다.",
        "choices": [
            {"label": 'api_key = os.getenv("OPENAI_API_KEY") or raise ValueError("키 없음")', "correct": False},
            {"label": 'if not api_key: raise ValueError("OPENAI_API_KEY not set")', "correct": True},
            {"label": 'api_key = os.environ["OPENAI_API_KEY"]', "correct": False},
            {"label": 'api_key = "hardcoded-key"', "correct": False},
        ],
    },
    {
        "title": "DataFrame 필터링 후 인덱스 접근", "bug_type_name": "KeyError",
        "file_name": "filter_data.py", "bug_line": 5,
        "buggy_code": 'import pandas as pd\ndf = pd.DataFrame({"score": [80, 90, 70], "pass": [True, True, False]})\npassed = df[df["pass"] == True]\nfirst_score = passed[0]["score"]\nprint(first_score)',
        "error_log": "KeyError: 0\nFile \"filter_data.py\", line 4",
        "hint": "필터링 후 인덱스는 원본 DataFrame의 인덱스를 유지합니다.",
        "choices": [
            {"label": 'first_score = passed.iloc[0]["score"]', "correct": True},
            {"label": 'first_score = passed.loc[0]["score"]', "correct": False},
            {"label": 'first_score = passed["score"][0]', "correct": False},
            {"label": 'first_score = passed.reset_index()[0]', "correct": False},
        ],
    },
    {
        "title": "리스트 컴프리헨션 조건 위치 오류", "bug_type_name": "SyntaxError",
        "file_name": "filter_list.py", "bug_line": 2,
        "buggy_code": 'numbers = [1, 2, 3, 4, 5, 6]\nevens = [if x % 2 == 0 x for x in numbers]\nprint(evens)',
        "error_log": "SyntaxError: invalid syntax\nFile \"filter_list.py\", line 2",
        "hint": "리스트 컴프리헨션에서 if 조건의 위치를 확인하세요.",
        "choices": [
            {"label": "evens = [x for x in numbers if x % 2 == 0]", "correct": True},
            {"label": "evens = [x if x % 2 == 0 for x in numbers]", "correct": False},
            {"label": "evens = [x for x in numbers where x % 2 == 0]", "correct": False},
            {"label": "evens = filter(x % 2 == 0, numbers)", "correct": False},
        ],
    },
    {
        "title": "sklearn train_test_split 비율 오류", "bug_type_name": "ValueError",
        "file_name": "split_data.py", "bug_line": 4,
        "buggy_code": 'from sklearn.model_selection import train_test_split\nimport numpy as np\nX = np.arange(100)\nX_train, X_test = train_test_split(X, test_size=80)\nprint(len(X_train))',
        "error_log": "ValueError: test_size=80 should be either positive and smaller than the number of samples 100\nFile \"split_data.py\", line 4",
        "hint": "test_size에 정수를 넣으면 샘플 수, 소수를 넣으면 비율입니다.",
        "choices": [
            {"label": "X_train, X_test = train_test_split(X, test_size=0.2)", "correct": True},
            {"label": "X_train, X_test = train_test_split(X, test_size=0.8)", "correct": False},
            {"label": "X_train, X_test = train_test_split(X, train_size=80)", "correct": False},
            {"label": "X_train, X_test = train_test_split(X, test_size=20)", "correct": False},
        ],
    },
    {
        "title": "PyTorch 텐서 gradient 누적", "bug_type_name": "LogicError",
        "file_name": "train_loop.py", "bug_line": 6,
        "buggy_code": 'import torch\nmodel = torch.nn.Linear(10, 1)\noptimizer = torch.optim.SGD(model.parameters(), lr=0.01)\nfor i in range(3):\n    loss = model(torch.randn(10)).sum()\n    loss.backward()\n    optimizer.step()',
        "error_log": "RuntimeError: gradient accumulates across iterations\nGradient grows unexpectedly",
        "hint": "매 iteration마다 gradient를 초기화해야 합니다.",
        "choices": [
            {"label": "optimizer.zero_grad() 를 loss.backward() 전에 추가", "correct": True},
            {"label": "optimizer.step() 을 제거", "correct": False},
            {"label": "loss.detach() 후 backward()", "correct": False},
            {"label": "model.zero_grad() 를 optimizer.step() 후에 추가", "correct": False},
        ],
    },
    {
        "title": "파일 경로 역슬래시 에러", "bug_type_name": "SyntaxError",
        "file_name": "load_model.py", "bug_line": 2,
        "buggy_code": 'import torch\npath = "C:\\Users\\model\\best.pt"\nmodel = torch.load(path)',
        "error_log": "SyntaxError: (unicode error) 'unicodeescape' codec\nFile \"load_model.py\", line 2",
        "hint": "Windows 경로에서 역슬래시는 이스케이프 문자로 처리됩니다.",
        "choices": [
            {"label": 'path = r"C:\\Users\\model\\best.pt"', "correct": True},
            {"label": 'path = "C://Users//model//best.pt"', "correct": False},
            {"label": 'path = "C:/Users/model/best.pt"', "correct": False},
            {"label": 'path = os.path.join("C:", "Users", "model", "best.pt")', "correct": False},
        ],
    },
    {
        "title": "재귀 함수 기저 조건 누락", "bug_type_name": "RecursionError",
        "file_name": "factorial.py", "bug_line": 2,
        "buggy_code": 'def factorial(n):\n    return n * factorial(n - 1)\n\nprint(factorial(5))',
        "error_log": "RecursionError: maximum recursion depth exceeded\nFile \"factorial.py\", line 2",
        "hint": "재귀 함수에는 반드시 종료 조건이 필요합니다.",
        "choices": [
            {"label": "if n <= 1: return 1 을 첫 줄에 추가", "correct": True},
            {"label": "if n == 0: return n 을 첫 줄에 추가", "correct": False},
            {"label": "return n * factorial(n + 1)", "correct": False},
            {"label": "sys.setrecursionlimit(10000) 추가", "correct": False},
        ],
    },
    {
        "title": "f-string 중괄호 이스케이프", "bug_type_name": "ValueError",
        "file_name": "template.py", "bug_line": 2,
        "buggy_code": 'name = "Alice"\nmsg = f"Hello {name}! Your score is {85}%"\nprint(msg)',
        "error_log": "정상 동작하지만 % 기호가 dict format으로 오해될 수 있음",
        "hint": "f-string 안에서 중괄호를 리터럴로 출력하려면 두 번 써야 합니다.",
        "choices": [
            {"label": 'msg = f"Hello {name}! Score: {{85}}%"', "correct": False},
            {"label": 'msg = f"Hello {name}! Score: {85}%"', "correct": True},
            {"label": 'msg = "Hello %s! Score: %d%%" % (name, 85)', "correct": False},
            {"label": 'msg = f"Hello " + name + "! Score: 85%"', "correct": False},
        ],
    },
    {
        "title": "glob 패턴 파일 없음", "bug_type_name": "FileNotFoundError",
        "file_name": "batch_load.py", "bug_line": 4,
        "buggy_code": 'import glob\nfiles = glob.glob("data/*.CSV")\nfor f in files:\n    print(f)',
        "error_log": "No files matched — files list is empty\nFile \"batch_load.py\", line 3",
        "hint": "Linux/Mac에서 glob 패턴은 대소문자를 구분합니다.",
        "choices": [
            {"label": 'files = glob.glob("data/*.csv")', "correct": True},
            {"label": 'files = glob.glob("data/**")', "correct": False},
            {"label": 'files = glob.glob("data/")', "correct": False},
            {"label": 'files = glob.glob("*.CSV", recursive=True)', "correct": False},
        ],
    },
    {
        "title": "zip 길이 불일치 데이터 손실", "bug_type_name": "LogicError",
        "file_name": "pair_data.py", "bug_line": 3,
        "buggy_code": 'labels = [0, 1, 2, 3, 4]\nfeatures = [[1,2], [3,4], [5,6]]\npairs = list(zip(labels, features))\nprint(len(pairs))',
        "error_log": "출력: 3 (기대값: 5)\n데이터 손실 발생",
        "hint": "zip은 가장 짧은 iterable 기준으로 멈춥니다.",
        "choices": [
            {"label": "from itertools import zip_longest; pairs = list(zip_longest(labels, features))", "correct": True},
            {"label": "pairs = list(zip(features, labels))", "correct": False},
            {"label": "pairs = [(labels[i], features[i]) for i in range(len(labels))]", "correct": False},
            {"label": "pairs = list(map(zip, labels, features))", "correct": False},
        ],
    },
    {
        "title": "클래스 메서드 self 누락", "bug_type_name": "TypeError",
        "file_name": "model_class.py", "bug_line": 4,
        "buggy_code": 'class Predictor:\n    def __init__(self, threshold):\n        self.threshold = threshold\n    def predict(score):\n        return score > self.threshold\n\np = Predictor(0.5)\nprint(p.predict(0.8))',
        "error_log": "TypeError: predict() takes 1 positional argument but 2 were given\nFile \"model_class.py\", line 4",
        "hint": "인스턴스 메서드의 첫 번째 인자는 항상 self여야 합니다.",
        "choices": [
            {"label": "def predict(self, score):", "correct": True},
            {"label": "def predict(score, self):", "correct": False},
            {"label": "@staticmethod\ndef predict(score):", "correct": False},
            {"label": "def predict(cls, score):", "correct": False},
        ],
    },
    {
        "title": "JSON dumps 직렬화 불가 타입", "bug_type_name": "TypeError",
        "file_name": "serialize.py", "bug_line": 4,
        "buggy_code": 'import json\nimport numpy as np\nresult = {"scores": np.array([0.9, 0.8, 0.7])}\nprint(json.dumps(result))',
        "error_log": "TypeError: Object of type ndarray is not JSON serializable\nFile \"serialize.py\", line 4",
        "hint": "numpy 배열은 기본 JSON 직렬화가 되지 않습니다.",
        "choices": [
            {"label": 'result = {"scores": np.array([0.9, 0.8, 0.7]).tolist()}', "correct": True},
            {"label": 'print(json.dumps(result, indent=2))', "correct": False},
            {"label": 'print(json.dumps(str(result)))', "correct": False},
            {"label": 'result["scores"] = list(result["scores"])', "correct": False},
        ],
    },
]


def _validate_problem(p: Dict[str, Any]) -> bool:
    for field in ["title", "bug_type_name", "buggy_code", "choices", "bug_line"]:
        if not p.get(field):
            return False
    choices = p.get("choices", [])
    if len(choices) != 4:
        return False
    if sum(1 for c in choices if c.get("correct")) != 1:
        return False
    if any(not c.get("label") for c in choices):
        return False
    lines = p.get("buggy_code", "").split("\n")
    if p["bug_line"] < 1 or p["bug_line"] > len(lines):
        return False
    return True


def _clean_problem(p: Dict[str, Any], step: int) -> Dict[str, Any]:
    p["fix_mode"] = "choice"
    p["step"] = step
    if not p.get("file_name"):
        p["file_name"] = "debug_me.py"
    if not p.get("error_log"):
        p["error_log"] = f'{p.get("bug_type_name", "Error")}: see line {p.get("bug_line", "?")}'
    if not p.get("hint"):
        p["hint"] = "에러 로그를 자세히 읽어보세요."
    random.shuffle(p["choices"])
    return p


async def generate_bug_problems(count: int = 10, difficulty: int = 1) -> List[Dict[str, Any]]:
    difficulty_desc = DIFFICULTY_DESC.get(difficulty, DIFFICULTY_DESC[1])
    prompt = PROMPT_TEMPLATE.format(count=count, difficulty_desc=difficulty_desc)
    problems = []

    try:
        client = _get_client()
        response = await client.chat.completions.create(
            model="gpt-4o-mini", temperature=0.85, max_tokens=4000,
            messages=[{"role": "user", "content": prompt}],
        )
        content = response.choices[0].message.content.strip()
        if content.startswith("```"):
            content = content.split("```")[1]
            if content.startswith("json"):
                content = content[4:]
        content = content.strip()

        raw = json.loads(content)
        if not isinstance(raw, list):
            raw = [raw]

        logger.info(f"[BugGen] GPT가 {len(raw)}개 문제 생성")
        step = 1
        for p in raw:
            if _validate_problem(p):
                problems.append(_clean_problem(p, step))
                step += 1

    except json.JSONDecodeError as e:
        logger.error(f"[BugGen] JSON 파싱 실패: {e}")
    except Exception as e:
        logger.error(f"[BugGen] GPT 호출 실패: {e}")

    if len(problems) < 20:
        fallback = [_clean_problem(dict(p), len(problems) + i + 1)
                    for i, p in enumerate(FALLBACK_PROBLEMS)]
        random.shuffle(fallback)
        needed = 20 - len(problems)
        # fallback이 부족하면 반복해서 체움
        while len(fallback) < needed:
            extra = [_clean_problem(dict(p), 0) for p in FALLBACK_PROBLEMS]
            random.shuffle(extra)
            fallback.extend(extra)
        problems.extend(fallback[:needed])

    random.shuffle(problems)
    return problems
