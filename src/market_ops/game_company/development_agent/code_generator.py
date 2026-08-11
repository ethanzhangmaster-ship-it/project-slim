from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
from datetime import datetime


@dataclass
class GeneratedCode:
    code_id: str
    file_name: str
    code: str = ""
    language: str = "C#"
    status: str = "generated"


class CodeGenerator:
    def __init__(self):
        self.generated_code: Dict[str, GeneratedCode] = {}

    def generate(self, script_name_or_genre, game_data: Dict[str, Any] = None, count: int = 1) -> Any:
        if game_data is None:
            game_data = {}
        
        if isinstance(script_name_or_genre, str) and count == 1:
            code = self._generate_script(script_name_or_genre, game_data)
            generated = GeneratedCode(
                code_id=f"code_{hash(script_name_or_genre) % 10000:04d}",
                file_name=script_name_or_genre,
                code=code,
                language="C#",
            )
            self.generated_code[generated.code_id] = generated
            return generated
        
        scripts = []
        script_names = ["GameManager.cs", "UIManager.cs", "EconomyManager.cs", "MergeManager.cs", "SaveSystem.cs"]
        
        for i in range(count):
            name = script_names[i % len(script_names)]
            code = self._generate_script(name, game_data)
            generated = GeneratedCode(
                code_id=f"code_{hash(name + str(i)) % 10000:04d}",
                file_name=name,
                code=code,
                language="C#",
            )
            self.generated_code[generated.code_id] = generated
            scripts.append(generated)
        
        return scripts

    def _generate_script(self, script_name: str, game_data: Dict[str, Any]) -> str:
        templates = {
            "GameManager.cs": self._generate_game_manager(),
            "UIManager.cs": self._generate_ui_manager(),
            "EconomyManager.cs": self._generate_economy_manager(game_data),
            "MergeManager.cs": self._generate_merge_manager(),
            "SaveSystem.cs": self._generate_save_system(),
            "AnalyticsManager.cs": self._generate_analytics_manager(),
        }
        
        return templates.get(script_name, "// Generated script")

    def _generate_game_manager(self) -> str:
        return """using UnityEngine;

public class GameManager : MonoBehaviour
{
    public static GameManager Instance;
    
    void Awake()
    {
        if (Instance == null) Instance = this;
        else Destroy(gameObject);
    }
    
    public void StartGame() { }
    public void PauseGame() { }
    public void ResumeGame() { }
}
"""

    def _generate_ui_manager(self) -> str:
        return """using UnityEngine;
using UnityEngine.UI;

public class UIManager : MonoBehaviour
{
    public Text currencyText;
    public Text energyText;
    
    public void UpdateCurrency(int amount) { }
    public void UpdateEnergy(int amount) { }
    public void ShowPanel(string panelName) { }
}
"""

    def _generate_economy_manager(self, game_data: Dict[str, Any]) -> str:
        max_energy = game_data.get("max_energy", 30)
        return f"""using UnityEngine;

public class EconomyManager : MonoBehaviour
{{
    public int coins;
    public int gems;
    public int energy;
    public int maxEnergy = {max_energy};
    
    public void AddCoins(int amount) {{ coins += amount; }}
    public void AddGems(int amount) {{ gems += amount; }}
    public bool SpendEnergy(int amount) {{
        if (energy >= amount) {{
            energy -= amount;
            return true;
        }}
        return false;
    }}
}}
"""

    def _generate_merge_manager(self) -> str:
        return """using UnityEngine;

public class MergeManager : MonoBehaviour
{
    public Grid grid;
    
    public void MergeItems(Vector2Int pos1, Vector2Int pos2) { }
    public bool CanMerge(Item item1, Item item2) { return true; }
    public Item CreateMergedItem(Item item1, Item item2) { return null; }
}
"""

    def _generate_save_system(self) -> str:
        return """using UnityEngine;

public class SaveSystem : MonoBehaviour
{
    public void SaveGame() { PlayerPrefs.Save(); }
    public void LoadGame() { }
    public void ResetGame() { PlayerPrefs.DeleteAll(); }
}
"""

    def _generate_analytics_manager(self) -> str:
        return """using UnityEngine;

public class AnalyticsManager : MonoBehaviour
{
    public void TrackEvent(string eventName, params object[] args) { }
    public void TrackScreen(string screenName) { }
    public void TrackPurchase(float amount, string item) { }
}
"""

    def generate_demo(self) -> GeneratedCode:
        return self.generate("EconomyManager.cs", {"max_energy": 30})
