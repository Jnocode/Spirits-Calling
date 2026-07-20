using UnrealBuildTool;
using System.Collections.Generic;

public class Spirits_CallingTarget : TargetRules
{
	public Spirits_CallingTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Game;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("SpiritsCalling");
	}
}
