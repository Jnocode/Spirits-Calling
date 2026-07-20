using UnrealBuildTool;
using System.Collections.Generic;

public class Spirits_CallingEditorTarget : TargetRules
{
	public Spirits_CallingEditorTarget(TargetInfo Target) : base(Target)
	{
		Type = TargetType.Editor;
		DefaultBuildSettings = BuildSettingsVersion.V7;
		IncludeOrderVersion = EngineIncludeOrderVersion.Latest;
		ExtraModuleNames.Add("SpiritsCalling");
	}
}
