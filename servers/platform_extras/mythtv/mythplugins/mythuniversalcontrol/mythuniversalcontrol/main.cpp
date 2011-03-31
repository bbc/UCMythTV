#include <iostream>
using namespace std;

#include <unistd.h>

#include <QDir>
#include <QApplication>

#include "ucui.h"

#include <mythcontext.h>
#include <mythdbcon.h>
#include <mythversion.h>
#include <lcddevice.h>
#include <myththemedmenu.h>
#include <mythpluginapi.h>
#include <mythuihelper.h>
#include <mythdialogs.h>

#define LOC_ERR QString("MythUniversalControl:MAIN Error: ")
#define LOC QString("MythUniversalControl:MAIN: ")

static void setupKeys(void)
{
}

static int RunPairingScreen(void)
{
    MythScreenStack *mainStack = GetMythMainWindow()->GetMainStack();
    PairingScreenUI *pairing = new PairingScreenUI(mainStack);

    if (pairing->Create())
    {
	mainStack->AddScreen(pairing);
	return 0;
    }
    else
    {
	delete pairing;
	return -1;
    }
}

int mythplugin_init(const char *libversion)
{
    if (!gContext->TestPopupVersion("mythuniversalcontrol", libversion,
                                    MYTH_BINARY_VERSION))
    {
        VERBOSE(VB_IMPORTANT,
                QString("libmythuniversalcontrol.so/main.o: binary version mismatch"));
        return -1;
    }

    setupKeys();

    return 0;
}

int mythplugin_run(void)
{
    return 0;
}

int mythplugin_config(void)
{
    return RunPairingScreen();
}

