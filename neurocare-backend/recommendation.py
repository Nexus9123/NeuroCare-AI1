from statistics import fmean


MODE_ORDER = ("easy", "medium", "hard")
RECENT_RESULT_LIMIT = 3


def recommend_game(completed_game: str) -> dict[str, str]:
    games = {
        "memory_card": "sequence_memory",
        "sequence_memory": "memory_card",
        "number_sequence": "memory_card",
        "sequence_recall": "memory_card",
        "stroop_test": "pattern_recognition",
        "pattern_recognition": "stroop_test",
        "reaction_time": "memory_card",
    }

    return {
        "next_game": games[completed_game],
        "reason": "Suggested as a varied cognitive training activity",
    }


def _get(result, field: str, default=None):
    """Read a result field from either a SQLAlchemy model or a dictionary."""
    if isinstance(result, dict):
        return result.get(field, default)
    return getattr(result, field, default)


def _age_based_start(game_name: str, user_age: int | None) -> dict:
    if user_age is not None and user_age < 45:
        mode = "hard"
        age_reason = "Your age group starts at Hard difficulty."
    elif user_age is not None and user_age <= 60:
        mode = "medium"
        age_reason = "Your age group starts at Medium difficulty."
    else:
        mode = "easy"
        age_reason = "Your age group starts at Easy difficulty."

    return {
        "game_name": game_name,
        "recommended_mode": mode,
        "recommended_level": 1,
        "reason": f"First recorded round: start at {mode.title()} level 1. {age_reason}",
        "previous_accuracy": None,
        "previous_score": None,
        "based_on_previous_result": False,
        "recent_results_used": 0,
        "average_recent_accuracy": None,
        "average_recent_score": None,
        "accuracy_trend": None,
        "average_recent_errors": None,
        "average_recent_time_seconds": None,
        "confidence": "low",
    }


def _move_difficulty(mode: str, level: int, max_level: int, direction: int):
    mode_index = MODE_ORDER.index(mode) if mode in MODE_ORDER else 0
    level = max(1, min(level, max_level))

    if direction > 0:
        if level < max_level:
            return mode, level + 1
        if mode_index < len(MODE_ORDER) - 1:
            return MODE_ORDER[mode_index + 1], 1
        return mode, max_level

    if level > 1:
        return mode, level - 1
    if mode_index > 0:
        return MODE_ORDER[mode_index - 1], 1
    return mode, 1


def recommend_level(
    game_name: str,
    previous_result=None,
    user_age: int | None = None,
    previous_results: list | None = None,
) -> dict:
    """Recommend difficulty using the latest three results for this user/game.

    Two consistently strong rounds increase difficulty by one step. Repeated
    weak rounds decrease it by one step. Mixed or limited evidence keeps the
    current setting. Age selects only the first-game starting difficulty.
    """
    if previous_results is None:
        history = [previous_result] if previous_result is not None else []
    else:
        history = [item for item in previous_results if item is not None]

    history = history[:RECENT_RESULT_LIMIT]
    if not history:
        return _age_based_start(game_name, user_age)

    latest = history[0]
    mode = _get(latest, "mode") or "easy"
    if mode not in MODE_ORDER:
        mode = "easy"
    level = max(1, int(_get(latest, "level") or 1))
    max_level = max(1, int(_get(latest, "max_level") or 10))

    accuracies = [float(_get(item, "accuracy") or 0) for item in history]
    scores = [float(_get(item, "score") or 0) for item in history]
    errors = [max(0, int(_get(item, "errors") or 0)) for item in history]
    completion_times = [
        float(_get(item, "completion_time_seconds") or 0)
        for item in history
        if float(_get(item, "completion_time_seconds") or 0) > 0
    ]

    # Recent rounds count more, while older rounds still help smooth noise.
    weights = (0.5, 0.3, 0.2)[:len(history)]
    weight_total = sum(weights)
    average_accuracy = sum(value * weight for value, weight in zip(accuracies, weights)) / weight_total
    average_score = sum(value * weight for value, weight in zip(scores, weights)) / weight_total
    average_errors = sum(value * weight for value, weight in zip(errors, weights)) / weight_total
    average_time = fmean(completion_times) if completion_times else None
    accuracy_trend = accuracies[0] - accuracies[-1] if len(accuracies) > 1 else 0.0

    strong_rounds = sum(
        accuracy >= 85 and score >= 80
        for accuracy, score in zip(accuracies, scores)
    )
    weak_rounds = sum(
        accuracy < 55 or score < 50
        for accuracy, score in zip(accuracies, scores)
    )

    confidence = "low" if len(history) == 1 else "medium" if len(history) == 2 else "high"
    latest_time = float(_get(latest, "completion_time_seconds") or 0)
    latest_errors = errors[0]
    same_level_history = [
        item for item in history[1:]
        if (_get(item, "mode") or "easy") == mode
        and int(_get(item, "level") or 1) == level
    ]
    comparable_times = [
        float(_get(item, "completion_time_seconds") or 0)
        for item in same_level_history
        if float(_get(item, "completion_time_seconds") or 0) > 0
    ]
    comparable_errors = [max(0, int(_get(item, "errors") or 0)) for item in same_level_history]
    notably_slower = bool(comparable_times) and latest_time > fmean(comparable_times) * 1.5
    error_spike = bool(comparable_errors) and latest_errors >= fmean(comparable_errors) + 2
    ready_to_advance = (
        len(history) >= 2
        and strong_rounds >= 2
        and average_accuracy >= 80
        and average_score >= 75
    )
    time_summary = f", average time {average_time:.1f}s" if average_time is not None else ""

    if ready_to_advance and error_spike:
        reason = (
            f"Your accuracy is strong, but you made more mistakes than in the same level before. "
            f"Repeating it once will help confirm the result. Average recent accuracy: {average_accuracy:.0f}%."
        )
    elif ready_to_advance and notably_slower:
        reason = (
            f"Your accuracy is strong, but this same level took much longer than before. "
            f"Repeating it once will help confirm a steady result. Average recent accuracy: {average_accuracy:.0f}%."
        )
    elif ready_to_advance:
        mode, level = _move_difficulty(mode, level, max_level, 1)
        reason = (
            f"Your last {len(history)} rounds show consistently strong results "
            f"(average accuracy {average_accuracy:.0f}%, average errors {average_errors:.1f}"
            f"{time_summary}). Moving up one step."
        )
    elif len(history) >= 2 and (weak_rounds >= 2 or (average_accuracy < 52 and average_score < 50)):
        mode, level = _move_difficulty(mode, level, max_level, -1)
        reason = (
            f"Your recent results show this game has been difficult "
            f"(recent average accuracy {average_accuracy:.0f}%). Moving down one step for practice."
        )
    elif len(history) == 1 and accuracies[0] >= 90 and scores[0] >= 85:
        mode, level = _move_difficulty(mode, level, max_level, 1)
        confidence = "low"
        reason = "Your first recorded result was very strong. Trying one step higher; this suggestion has low confidence."
    elif len(history) == 1 and (accuracies[0] < 45 or scores[0] < 40):
        mode, level = _move_difficulty(mode, level, max_level, -1)
        confidence = "low"
        reason = "Your first recorded result suggests an easier practice step. This suggestion has low confidence."
    else:
        trend_text = "improving" if accuracy_trend >= 8 else "declining" if accuracy_trend <= -8 else "steady"
        reason = (
            f"Your recent performance is {trend_text} (average accuracy "
            f"{average_accuracy:.0f}%). Repeating this level gives us more evidence before changing difficulty."
        )

    return {
        "game_name": game_name,
        "recommended_mode": mode,
        "recommended_level": level,
        "reason": reason,
        "previous_accuracy": accuracies[0],
        "previous_score": scores[0],
        "based_on_previous_result": True,
        "recent_results_used": len(history),
        "average_recent_accuracy": round(average_accuracy, 1),
        "average_recent_score": round(average_score, 1),
        "accuracy_trend": round(accuracy_trend, 1),
        "average_recent_errors": round(average_errors, 1),
        "average_recent_time_seconds": round(average_time, 2) if average_time is not None else None,
        "confidence": confidence,
    }
