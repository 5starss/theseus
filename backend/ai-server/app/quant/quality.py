from typing import Any, Dict, List


def build_backtest_quality_flags(summary: Dict[str, Any]) -> Dict[str, Any]:
    trade_count = int(summary.get("trade_count", 0))
    sharpe = float(summary.get("sharpe", 0.0))
    dir_acc = float(summary.get("directional_accuracy_all", 0.0))
    dir_base = float(summary.get("directional_baseline_all", 0.0))
    exposure = float(summary.get("exposure", 0.0))

    flags: List[str] = []
    if trade_count < 100:
        flags.append("LOW_SAMPLE_SIZE")
    if sharpe > 8.0:
        flags.append("EXTREME_SHARPE")
    if not (0.0 <= dir_acc <= 1.0 and 0.0 <= dir_base <= 1.0):
        flags.append("DIRECTION_METRIC_OUT_OF_RANGE")
    if dir_acc < dir_base:
        flags.append("DIRECTION_UNDER_BASELINE")
        if (dir_base - dir_acc) > 0.10:
            flags.append("DIRECTION_SIGNIFICANTLY_UNDER_BASELINE")
    if abs(dir_acc - dir_base) > 0.35:
        flags.append("DIRECTION_GAP_TOO_LARGE")
    if exposure < 0.02:
        flags.append("LOW_EXPOSURE")

    if "LOW_SAMPLE_SIZE" in flags or "DIRECTION_METRIC_OUT_OF_RANGE" in flags:
        confidence_band = "low"
    elif "EXTREME_SHARPE" in flags or "DIRECTION_GAP_TOO_LARGE" in flags:
        confidence_band = "medium"
    else:
        confidence_band = "high"

    reason_map = {
        "LOW_SAMPLE_SIZE": f"거래 표본 수 부족(trade_count={trade_count})",
        "EXTREME_SHARPE": f"샤프 비정상적으로 높음(sharpe={sharpe:.2f})",
        "DIRECTION_METRIC_OUT_OF_RANGE": "방향성 지표 범위 이상",
        "DIRECTION_UNDER_BASELINE": f"방향성 정확도가 기준선 미달(acc={dir_acc:.3f}, base={dir_base:.3f})",
        "DIRECTION_SIGNIFICANTLY_UNDER_BASELINE": f"방향성 정확도 기준선 대비 큰 열위(gap={dir_base - dir_acc:.3f})",
        "DIRECTION_GAP_TOO_LARGE": f"방향성 지표 편차 과다(gap={abs(dir_acc - dir_base):.3f})",
        "LOW_EXPOSURE": f"노출도 부족(exposure={exposure:.4f})",
    }
    reasons = [reason_map[f] for f in flags if f in reason_map]

    hard_unreliable_flags = {
        "LOW_SAMPLE_SIZE",
        "DIRECTION_METRIC_OUT_OF_RANGE",
        "DIRECTION_SIGNIFICANTLY_UNDER_BASELINE",
        "LOW_EXPOSURE",
    }
    is_reliable_for_llm = (confidence_band != "low") and not any(
        f in hard_unreliable_flags for f in flags
    )

    return {
        "flags": flags,
        "reasons": reasons,
        "confidence_band": confidence_band,
        "is_reliable_for_llm": is_reliable_for_llm,
    }
