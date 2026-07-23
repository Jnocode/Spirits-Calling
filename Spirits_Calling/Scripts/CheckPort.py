import unreal

def check_python_settings():
    # Try to find the settings object directly by path
    # This is the standard path for the Class Default Object (CDO) of the settings
    settings_path = "/Script/PythonScriptPlugin.Default__PythonScriptPluginSettings"
    settings = unreal.find_object(None, settings_path)
    
    if not settings:
        print(f"Error: Could not find settings object at {settings_path}")
        return

    print("-" * 30)
    print(f"Settings Object: {settings}")
    
    # helper to safely get property
    def get_prop(name):
        try:
            return settings.get_editor_property(name)
        except Exception:
            return "(Not Found)"

    print(f"Remote Execution Enabled: {get_prop('bRemoteExecution')}")
    print(f"Bind Address: {get_prop('RemoteExecutionMulticastBindAddress')}")
    print(f"Command Port: {get_prop('RemoteExecutionCommandPort')}")
    print("-" * 30)
    
    # Also dump all properties to see if names changed
    print("All Properties:")
    for prop in dir(settings):
        if not prop.startswith('_') and not callable(getattr(settings, prop)):
             # Filter out generic stuff
             print(f"  {prop}")

if __name__ == "__main__":
    check_python_settings()
