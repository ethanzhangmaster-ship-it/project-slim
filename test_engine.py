from creative_remix_engine.core.remix_engine import RemixEngine

engine = RemixEngine(game_code="P04")
result = engine.generate(template="bomb_15s", target_ratio="9X16", count=5, build_video=False)

print("\n--- TOP 5 Predictions ---")
for p in result["predictions"][:5]:
    print(f"{p['creative_id']}: Score={p['overall_score']:.1f} Hook={p['hook_score']:.1f} Rec={p['recommendation']}")
