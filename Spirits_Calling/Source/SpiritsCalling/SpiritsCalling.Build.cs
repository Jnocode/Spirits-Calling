using UnrealBuildTool;

public class SpiritsCalling : ModuleRules
{
	public SpiritsCalling(ReadOnlyTargetRules Target) : base(Target)
	{
		PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;

		PublicDependencyModuleNames.AddRange(new string[]
		{
			"Core",
			"CoreUObject",
			"Engine",
			"InputCore",
			"EnhancedInput",
			"UMG",
			"Slate",
			"SlateCore",
			"AIModule",
			"NavigationSystem",
			"HeadMountedDisplay",
			"XRBase",
			"NetCore",
			"Niagara",
			"OnlineSubsystem",
			"OnlineSubsystemUtils"
		});

		// Steam is an optional runtime backend. Keep the module dynamically loaded
		// so missing Steam client/plugin availability falls back without preventing
		// PC or LAN builds from compiling and running.
		DynamicallyLoadedModuleNames.Add("OnlineSubsystemSteam");
	}
}
