property defaultFolderAction : "ASK" -- ASK, INSIDE, LEVEL
property defaultAliasAction : "ASK" -- ASK, TARGET, ALIAS
property runLockDir : "/tmp/term-at-target.lock"

on run {input, parameters}
	if my acquireRunLock() is false then return {}
	
	try
		set targetPath to my resolveTargetPath(input)
		if targetPath is not missing value then
			if targetPath is not "" then
				do shell script "/usr/bin/open -a Terminal " & quoted form of targetPath
			end if
		end if
		
		my releaseRunLock()
		return {}
	on error errMsg number errNum
		my releaseRunLock()
		if errNum is -128 then return {}
		error errMsg number errNum
	end try
end run

on resolveTargetPath(input)
	if (count of input) is 0 then
		set selectedFolder to choose folder with prompt "Choose a folder to open in Terminal:"
		return POSIX path of selectedFolder
	end if
	
	set selectedItem to item 1 of input
	
	tell application "Finder"
		set isAliasFile to false
		set aliasTarget to missing value
		
		try
			set aliasTarget to original item of selectedItem
			set isAliasFile to true
		end try
		
		if isAliasFile then
			if my useAliasTarget() then
				return my pathForItem(aliasTarget)
			else
				return POSIX path of (container of selectedItem as alias)
			end if
		else
			return my pathForItem(selectedItem)
		end if
	end tell
end resolveTargetPath

on pathForItem(theItem)
	tell application "Finder"
		set itemPath to POSIX path of (theItem as alias)
	end tell
	
	if my isDirectory(itemPath) then
		if my folderOpenMode() is "LEVEL" then
			tell application "Finder"
				return POSIX path of (container of theItem as alias)
			end tell
		else
			return itemPath
		end if
	else
		tell application "Finder"
			return POSIX path of (container of theItem as alias)
		end tell
	end if
end pathForItem

on isDirectory(p)
	set out to do shell script "/bin/test -d " & quoted form of p & " && /bin/echo 1 || /bin/echo 0"
	return (out is "1")
end isDirectory

on useAliasTarget()
	if defaultAliasAction is "TARGET" then return true
	if defaultAliasAction is "ALIAS" then return false
	
	set choice to choose from list {"Open Terminal at TARGET location", "Open Terminal at ALIAS location"} with prompt "You selected an alias. Where should Terminal open?" default items {"Open Terminal at TARGET location"} OK button name "OK" cancel button name "Cancel"
	if choice is false then error number -128
	return ((item 1 of choice) is "Open Terminal at TARGET location")
end useAliasTarget

on folderOpenMode()
	if defaultFolderAction is "INSIDE" then return "INSIDE"
	if defaultFolderAction is "LEVEL" then return "LEVEL"
	
	set choice to choose from list {"Open Terminal INSIDE this folder", "Open Terminal at this folder's LEVEL"} with prompt "You selected a folder. Where should Terminal open?" default items {"Open Terminal INSIDE this folder"} OK button name "OK" cancel button name "Cancel"
	if choice is false then error number -128
	if (item 1 of choice) is "Open Terminal at this folder's LEVEL" then return "LEVEL"
	return "INSIDE"
end folderOpenMode

on acquireRunLock()
	set nowEpoch to (do shell script "/bin/date +%s") as integer
	try
		do shell script "/bin/mkdir " & quoted form of runLockDir
		return true
	on error
		try
			set lockEpoch to (do shell script "/usr/bin/stat -f %m " & quoted form of runLockDir) as integer
			if (nowEpoch - lockEpoch) > 15 then
				do shell script "/bin/rmdir " & quoted form of runLockDir
				do shell script "/bin/mkdir " & quoted form of runLockDir
				return true
			end if
		end try
		return false
	end try
end acquireRunLock

on releaseRunLock()
	try
		do shell script "/bin/rmdir " & quoted form of runLockDir
	end try
end releaseRunLock
