#ifndef UCUI_H_
#define UCUI_H_

#include <QString>
#include <QObject>

// myth
#include <mythscreentype.h>

#include "PairingScreen_p.h"

class PairingScreenUI : public MythScreenType
{
    Q_OBJECT

  public:
    PairingScreenUI(MythScreenStack *parentStack);
    ~PairingScreenUI();

    bool Create();


  private slots:
    void CloseNow();
    void refreshCode();
    void refreshVersion();
    void deauthenticateClient(MythUIButtonListItem *);
    void refreshButtons();

  private:

    MythUIBusyDialog *m_busyPopup;
    MythScreenStack  *m_popupStack;
    MythUIText       *m_pairingcodetext;
    MythUIText       *m_versiontext;
    MythUIButtonList *m_authenticatedclients;
    
    UkCoBbcUniversalControlPairingScreenInterface *m_dbus_pairingscreen;
};

#endif
