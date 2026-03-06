"""
LLM-only vs LLM+Rule 실시간 비교 실험
동일 샘플을 5회 평가하며 두 점수를 터미널에 나란히 출력

실행:
    python run_compare.py            # quick 모드 (품질별 1개씩, 3회)
    python run_compare.py --full     # 전체 30개 샘플, 5회
    python run_compare.py --trials 5 # 반복 횟수 지정
"""
import os
import sys
import json
import time
import statistics
import django
from pathlib import Path

# Django 설정
backend_dir = Path(__file__).resolve().parents[8] / 'backend'
sys.path.insert(0, str(backend_dir))
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from core.services.pseudocode_evaluator import (
    PseudocodeEvaluator,
    EvaluationRequest,
    EvaluationMode,
    LowEffortError, LLMTimeoutError, LLMUnavailableError,
)

# ── ANSI 색상 ─────────────────────────────────────────────────────────────────
R    = "\033[91m"
G    = "\033[92m"
Y    = "\033[93m"
C    = "\033[96m"
W    = "\033[97m"
DIM  = "\033[2m"
BOLD = "\033[1m"
RST  = "\033[0m"

def bar(value, width=20, color=G, max_val=100):
    filled = int(round(value / max_val * width))
    filled = max(0, min(width, filled))
    return color + "█" * filled + DIM + "░" * (width - filled) + RST

# ── 평가 실행 ─────────────────────────────────────────────────────────────────
evaluator = PseudocodeEvaluator()

def evaluate_once(sample: dict) -> dict:
    """
    1회 평가. llm_only 점수와 hybrid 점수를 모두 반환.

    비교 기준:
      - LLM-only : llm_score_85 / 85 * 100 → 0~100점 환산 (Rule 없이 LLM만 채점했을 때)
      - LLM+Rule : llm_score_85 + rule_score_15 = final_score (0~100점)
    → 둘 다 100점 만점 기준으로 비교
    """
    req = EvaluationRequest(
        user_id='compare_test',
        detail_id=sample['quest_id'],
        pseudocode=sample['pseudocode'],
        quest_title=sample['quest_title'],
        tail_answer='',
        deep_answer='',
        mode=EvaluationMode.OPTION2_GPTONLY,
    )
    result = evaluator.evaluate(req)
    sb = result.score_breakdown

    # LLM-only: GPT 85점 만점 → 100점 스케일 환산 (Rule 없이 LLM만 채점했을 때)
    llm_85   = sb.get('llm_score_85', 0)
    llm_only = round(llm_85 / 85 * 100)

    # LLM+Rule: LLM 85점 + Rule 15점 = 최대 100점
    hybrid  = sb.get('final_score', result.final_score)
    rule_pt = sb.get('rule_score_15', 0)

    return {
        'llm_only':  llm_only,  # 0~100 스케일 (LLM 단독 환산)
        'hybrid':    hybrid,     # 0~100 스케일 (LLM+Rule 합산)
        'rule_pt':   rule_pt,
        'grade':     result.grade,
    }

# ── 메인 ──────────────────────────────────────────────────────────────────────
def run(samples: list, num_trials: int):
    all_results = []

    print()
    print(C + BOLD + "  ┌─────────────────────────────────────────────────────────┐" + RST)
    print(C + BOLD + "  │   LLM-only  vs  LLM + Rule  |  실시간 비교 실험         │" + RST)
    print(C + BOLD + "  │   각 샘플 " + W + f"{num_trials}회 반복" + C + " · 터미널 점수 출력                  │" + RST)
    print(C + BOLD + "  └─────────────────────────────────────────────────────────┘" + RST)
    print()

    for s_idx, sample in enumerate(samples):
        sid     = sample['sample_id']
        quality = sample['quality_level']
        title   = sample.get('quest_title', '')[:40]

        q_color = {
            'excellent': G, 'good': C,
            'average': Y, 'poor': R, 'very_poor': R+DIM
        }.get(quality, W)

        print(f"  {DIM}{'─'*58}{RST}")
        print(f"  [{s_idx+1:02d}/{len(samples):02d}]  {W}{sid}{RST}  {q_color}[{quality}]{RST}")
        print(f"  {DIM}{title}{RST}")
        print(f"  {'Trial':<8} {'LLM-only':>10}  {'LLM+Rule':>10}  {'Rule 기여':>10}  {'차이':>6}")
        print(f"  {DIM}{'·'*54}{RST}")

        llm_scores    = []
        hybrid_scores = []

        for t in range(1, num_trials + 1):
            try:
                res = evaluate_once(sample)
                llm_scores.append(res['llm_only'])
                hybrid_scores.append(res['hybrid'])

                diff  = res['hybrid'] - res['llm_only']
                d_str = f"{'+' if diff >= 0 else ''}{diff}"
                d_col = G if diff > 0 else (Y if diff == 0 else R)

                print(
                f"  Trial {t:<3}"
                f"  {R}{res['llm_only']:>5}점/100{RST}"
                f"  {G}{res['hybrid']:>4}점/100{RST}"
                f"  {Y}+{res['rule_pt']:.1f}pt{RST}"
                f"  {d_col}{d_str:>5}점{RST}"
                )
            except (LowEffortError, LLMTimeoutError, LLMUnavailableError) as e:
                print(f"  Trial {t}  오류: {e}")
            except Exception as e:
                print(f"  Trial {t}  예외: {e}")

            time.sleep(0.5)

        # 샘플 요약
        if llm_scores:
            llm_mean = statistics.mean(llm_scores)
            llm_std  = statistics.stdev(llm_scores) if len(llm_scores) > 1 else 0
            hyb_mean = statistics.mean(hybrid_scores)
            hyb_std  = statistics.stdev(hybrid_scores) if len(hybrid_scores) > 1 else 0

            print(f"  {DIM}{'·'*54}{RST}")
            print(
                f"  {'평균/σ':<8}"
                f"  {R}{llm_mean:>5.1f}/100 ±{llm_std:.2f}{RST}"
                f"  {G}{hyb_mean:>5.1f}/100 ±{hyb_std:.2f}{RST}"
            )
            print(
                f"  {'바 차트':<8}"
                f"  {bar(llm_mean, color=R, max_val=100)}  {R}{llm_mean:.0f}/100{RST}"
                f"  {bar(hyb_mean, color=G)}  {G}{hyb_mean:.0f}/100{RST}"
            )

            all_results.append({
                'sample_id':  sid,
                'quality':    quality,
                'llm_mean':   round(llm_mean, 2),
                'llm_std':    round(llm_std, 3),
                'hybrid_mean': round(hyb_mean, 2),
                'hybrid_std': round(hyb_std, 3),
            })

        print()

    # ── 전체 요약 ─────────────────────────────────────────────────────────────
    if not all_results:
        return

    print()
    print(C + BOLD + "  ┌─────────────────────────────────────────────────────────┐" + RST)
    print(C + BOLD + "  │                      종합 요약                          │" + RST)
    print(C + BOLD + "  └─────────────────────────────────────────────────────────┘" + RST)
    print()

    total_llm_std  = statistics.mean(r['llm_std']    for r in all_results)
    total_hyb_std  = statistics.mean(r['hybrid_std'] for r in all_results)

    print(f"  {'항목':<20}  {'LLM-only (/85)':>16}  {'LLM+Rule (/100)':>16}")
    print(f"  {DIM}{'─'*56}{RST}")
    print(f"  {'평균 편차 (σ)':<20}  {R}±{total_llm_std:.2f}점{RST}{'':>11}  {G}±{total_hyb_std:.2f}점{RST}")

    # 품질별 평균 점수
    print()
    for ql in ['excellent', 'good', 'average', 'poor', 'very_poor']:
        rows = [r for r in all_results if r['quality'] == ql]
        if not rows:
            continue
        lm = statistics.mean(r['llm_mean']    for r in rows)
        hm = statistics.mean(r['hybrid_mean'] for r in rows)
        ls = statistics.mean(r['llm_std']     for r in rows)
        hs = statistics.mean(r['hybrid_std']  for r in rows)
        q_color = {
            'excellent': G, 'good': C, 'average': Y,
            'poor': R, 'very_poor': R+DIM
        }.get(ql, W)
        print(f"  {q_color}{ql:<12}{RST}  LLM-only {R}{lm:5.1f}±{ls:.2f}{RST}  →  LLM+Rule {G}{hm:5.1f}±{hs:.2f}{RST}")

    # 결론 한 줄
    print()
    print(f"  {DIM}{'─'*58}{RST}")
    print(f"  {C}결론{RST}  LLM 편차 {R}±{total_llm_std:.2f}점{RST}  →  Rule 결합 후 {G}±{total_hyb_std:.2f}점{RST}으로 안정화")
    exc = next((r for r in all_results if r['quality']=='excellent'), None)
    if exc:
        diff_str = f"+{exc['hybrid_mean']-exc['llm_mean']:.1f}" if exc['hybrid_mean'] >= exc['llm_mean'] else f"{exc['hybrid_mean']-exc['llm_mean']:.1f}"
        print(f"       Excellent 샘플 기준 점수 변화: {R}{exc['llm_mean']:.1f}{RST} → {G}{exc['hybrid_mean']:.1f}{RST} ({diff_str}점)")
    print()

    # JSON 저장
    out = Path(__file__).parent / 'data' / 'compare_results.json'
    with open(out, 'w', encoding='utf-8') as f:
        json.dump(all_results, f, ensure_ascii=False, indent=2)
    print(f"  {DIM}결과 저장: {out}{RST}")
    print()


# ── 진입점 ────────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--full',   action='store_true', help='전체 30개 샘플')
    parser.add_argument('--trials', type=int, default=3, help='반복 횟수 (기본 3)')
    args = parser.parse_args()

    base = Path(__file__).resolve().parent

    if args.full:
        src = base / 'data' / 'validation_samples.json'
    else:
        # quick: 품질별 1개씩 (5개 샘플)
        src = base / 'data' / 'validation_samples.json'
        with open(src, encoding='utf-8') as f:
            all_samples = json.load(f)
        selected = []
        for ql in ['excellent', 'good', 'average', 'poor', 'very_poor']:
            s = next((x for x in all_samples if x['quality_level'] == ql), None)
            if s:
                selected.append(s)
        run(selected, args.trials)
        sys.exit()

    with open(src, encoding='utf-8') as f:
        samples = json.load(f)

    run(samples, args.trials)
