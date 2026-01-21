package stt;

import java.io.File;
import java.net.InetSocketAddress;
import java.util.HashMap;
import java.util.Map;

// Imports Audio
import javax.sound.sampled.AudioFormat;
import javax.sound.sampled.AudioSystem;
import javax.sound.sampled.DataLine;
import javax.sound.sampled.TargetDataLine;

// Imports Vosk
import org.vosk.Model;
import org.vosk.Recognizer;

// Imports WebSocket (Le fichier que tu viens d'ajouter)
import org.java_websocket.WebSocket;
import org.java_websocket.handshake.ClientHandshake;
import org.java_websocket.server.WebSocketServer;

public class AppReseau extends WebSocketServer {

    // --- CONFIGURATION ---
    private static final String DOSSIER_BDD = "stt/database_signes/";
    // ⚠️ Vérifie que ce chemin est bon !
    private static final String CHEMIN_MODELE = "stt/model/vosk-model-small-fr-0.22"; 
    
    private static Map<String, String> dictionnaire = new HashMap<>();
    private static AppReseau monServeur; 

    // Constructeur du serveur
    public AppReseau(InetSocketAddress address) {
        super(address);
    }

    public static void main(String[] args) {
        // J'ai enlevé la ligne LibVosk.setLogLevel pour éviter ton erreur.

        // 1. Remplissage du Dictionnaire
        dictionnaire.put("accepter", "Accept1n.LSF");
        dictionnaire.put("étranger", "Abroad1n.LSF");
        dictionnaire.put("un peu",   "A_little1n.LSF");

        // 2. Démarrage du Serveur Web (Port 8887)
        String host = "localhost";
        int port = 8887;
        monServeur = new AppReseau(new InetSocketAddress(host, port));
        monServeur.start();
        System.out.println("📡 SERVEUR LANCE : J'attends l'avatar sur le port " + port);

        // 3. Démarrage de l'écoute Vocale
        lancerReconnaissanceVocale();
    }

    public static void lancerReconnaissanceVocale() {
        try (Model model = new Model(CHEMIN_MODELE)) {
            Recognizer recognizer = new Recognizer(model, 16000);
            
            AudioFormat format = new AudioFormat(16000, 16, 1, true, false);
            DataLine.Info info = new DataLine.Info(TargetDataLine.class, format);
            
            if (!AudioSystem.isLineSupported(info)) {
                System.out.println("❌ Erreur Micro !");
                return;
            }

            TargetDataLine microphone = (TargetDataLine) AudioSystem.getLine(info);
            microphone.open(format);
            microphone.start();

            System.out.println("🎤 MICRO PRET : Dis 'Accepter' !");

            byte[] buffer = new byte[4096];
            int nbytes;
            while ((nbytes = microphone.read(buffer, 0, buffer.length)) >= 0) {
                if (recognizer.acceptWaveForm(buffer, nbytes)) {
                    verifierMotsCles(recognizer.getResult());
                }
            }
        } catch (Exception e) {
            e.printStackTrace();
        }
    }

    public static void verifierMotsCles(String json) {
        String phrase = json.toLowerCase(); 

        for (String mot : dictionnaire.keySet()) {
            if (phrase.contains(mot)) {
                String nomFichier = dictionnaire.get(mot);
                File f = new File(DOSSIER_BDD + nomFichier + ".sigml");

                if (f.exists()) {
                    System.out.println("✅ RECONNU : " + mot.toUpperCase() + " -> Envoi à l'avatar...");
                    // Envoi du message à la page Web
                    monServeur.broadcast(nomFichier + ".sigml"); 
                }
            }
        }
    }

    // --- Méthodes obligatoires pour WebSocketServer ---
    @Override
    public void onOpen(WebSocket conn, ClientHandshake handshake) {
        System.out.println("🔌 L'avatar est connecté !");
    }
    @Override
    public void onClose(WebSocket conn, int code, String reason, boolean remote) {
        System.out.println("❌ L'avatar s'est déconnecté.");
    }
    @Override
    public void onMessage(WebSocket conn, String message) {
        // On ne fait rien quand l'avatar parle, on veut juste lui parler.
    }
    @Override
    public void onError(WebSocket conn, Exception ex) {
        ex.printStackTrace();
    }
    @Override
    public void onStart() {
        System.out.println("✅ Le système de communication est prêt.");
    }
}