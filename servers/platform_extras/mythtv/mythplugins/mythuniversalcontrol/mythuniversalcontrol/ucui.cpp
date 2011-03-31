#include <QStringList>
#include <QMetaType>
#include <QTimer>
#include <qregexp.h>

#include <mythcontext.h>
#include <mythuibuttontree.h>
#include <mythuiimage.h>
#include <mythuitext.h>
#include <mythuistatetype.h>
#include <mythmainwindow.h>
#include <mythdialogbox.h>
#include <mythgenerictree.h>
#include <mythdirs.h>

#include "ucui.h"

PairingScreenUI::PairingScreenUI(MythScreenStack *parent)
    : MythScreenType(parent, "PairingScreenUI")
    , m_busyPopup(0)
    , m_dbus_pairingscreen ( new UkCoBbcUniversalControlPairingScreenInterface("uk.co.bbc.UniversalControl",
									       "/UniversalControl/PairingScreen",
									       QDBusConnection::sessionBus(), 
									       this))
{
    m_popupStack = GetMythMainWindow()->GetStack("popup stack");
    
    QObject::connect(m_dbus_pairingscreen, SIGNAL(shouldStopDisplay()),
		     this, SLOT(Close()));
    QObject::connect(m_dbus_pairingscreen, SIGNAL(clientListChanged()),
		     this, SLOT(refreshButtons()));
}

PairingScreenUI::~PairingScreenUI()
{
    m_dbus_pairingscreen->willClose();
    delete m_dbus_pairingscreen;
}

bool PairingScreenUI::Create()
{
    if (!LoadWindowFromXML("pairingscreen-ui.xml","pairingscreenui",this))
	return false;
    
    bool err = false;
    UIUtilE::Assign(this, m_pairingcodetext, "ucpairingcode", &err);
    UIUtilE::Assign(this, m_versiontext, "version", &err);
    UIUtilE::Assign(this, m_authenticatedclients, "AuthenticatedClients", &err);

    if (err) 
    {
	VERBOSE(VB_IMPORTANT, "Cannot load UC Pairing Code Screen");
	return false;
    }

    connect(m_authenticatedclients, SIGNAL(itemClicked(MythUIButtonListItem *)),
	    this, SLOT(deauthenticateClient(MythUIButtonListItem *)));

    this->refreshCode();
    this->refreshVersion();

    return true;
}

void PairingScreenUI::refreshButtons()
{
    QDBusPendingReply<QStringList> reply = m_dbus_pairingscreen->getClientList();
    reply.waitForFinished();
    if (reply.isError())
	return;

    QStringList clients = reply.argumentAt<0>();
    MythUIButtonListItem *item;

    m_authenticatedclients->Reset();

    QStringListIterator iterator(clients);
    QRegExp re = QRegExp("(.+):(.+)");
    while(iterator.hasNext())
    {
	QString tmp = iterator.next();
	VERBOSE(VB_IMPORTANT, tmp);
	if (re.exactMatch(tmp))
	{
	    item = new MythUIButtonListItem(m_authenticatedclients,
					    QString("Deauthenticate \"%1\"").arg(re.cap(2)),
					    QVariant(re.cap(1)));
	}
    }
    
    BuildFocusList();
}

void PairingScreenUI::deauthenticateClient(MythUIButtonListItem *item)
{
    VERBOSE(VB_IMPORTANT, QString("Button \"%1\" Clicked").arg(item->GetText()));

    QDBusPendingReply<> reply = m_dbus_pairingscreen->deleteClient(item->GetData().toString());
    reply.waitForFinished();
}

void PairingScreenUI::CloseNow()
{
  VERBOSE(VB_IMPORTANT, "Recieved SHOULD STOP DISPLAY signal");

  Close();
}

void PairingScreenUI::refreshCode()
{
    m_pairingcodetext->SetText("");

    this->refreshButtons();

    QDBusPendingReply<QString> reply = m_dbus_pairingscreen->willOpen();
    reply.waitForFinished();
    if (!reply.isError())
    {
	m_pairingcodetext->SetText(reply.argumentAt<0>());
    }
    else
    {
	m_pairingcodetext->SetText("ERROR!");
    }    
}

void PairingScreenUI::refreshVersion()
{
    QDBusPendingReply<QString> reply = m_dbus_pairingscreen->versionInfo();
    reply.waitForFinished();
    if (!reply.isError())
    {
	m_versiontext->SetText(reply.argumentAt<0>());
    }
    else
    {
	m_versiontext->SetText("<No Known Server>");
    }    
}

//#include "ucui.moc"
