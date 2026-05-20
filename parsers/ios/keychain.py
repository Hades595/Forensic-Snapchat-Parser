import plistlib

def process_keychain(keychain_path: str) -> str:
    try:
        with open(keychain_path, "rb") as infile:
            plist = plistlib.load(infile)
            
            for i in plist["genp"]:
                try:
                    if i["gena"].decode('ASCII') == "egocipher.key.avoidkeyderivation":
                        #print(i['v_Data'].hex())
                        return i['v_Data'].hex()
                except:
                    continue    
    except Exception as e:
        return f"Keychain processing failed: {str(e)}"