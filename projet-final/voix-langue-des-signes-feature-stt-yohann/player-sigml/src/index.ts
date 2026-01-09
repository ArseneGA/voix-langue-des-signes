import { loadSigmlExample, parseSigml } from "./sigml/index.js";
import type { Sign } from "./sigml/types.js";

/**
 * Phase 2 - Core SiGML (Parser)
 * 
 * Périmètre :
 * - Lire un fichier XML SiGML (.sigml)
 * - Parser le XML en structure interne Sign (TypeScript)
 * - Extraire : gloss, langue, configurations de main, localisation, mouvements
 * - Support initial : signes manuels uniquement (mains/bras)
 * 
 * Ce qui n'est PAS dans la Phase 2 :
 * - Animation 3D (Phase 4)
 * - Mapping SiGML → Rig (Phase 3)
 * - Chargement d'avatar (Phase 1)
 * - Interface utilisateur (Phase 5)
 * 
 * Résultat attendu : une structure Sign propre, prête pour les phases suivantes.
 */

function logSignDetails(name: string, sign: Sign): void {
  console.group(`✅ Signe parsé : ${sign.gloss} (${name})`);
  
  console.log("📋 Métadonnées:", {
    gloss: sign.gloss,
    langue: sign.language ?? "non spécifiée",
  });

  console.log(`✋ Configurations de main (${sign.manual.handConfigurations.length}):`);
  sign.manual.handConfigurations.forEach((hc, i) => {
    console.log(`  ${i + 1}. Main ${hc.hand}:`, {
      handshape: hc.handshape ?? "non spécifié",
      thumbPos: hc.thumbPos ?? "non spécifié",
      palmor: hc.palmor ?? "non spécifié",
      extfidir: hc.extfidir ?? "non spécifié",
      mainBend: hc.mainBend ?? "non spécifié",
    });
  });

  if (sign.manual.location) {
    console.log("📍 Localisation:", {
      body: sign.manual.location.body,
      side: sign.manual.location.side ?? "non spécifié",
    });
  } else {
    console.log("📍 Localisation: non spécifiée");
  }

  console.log(`🎬 Mouvements (${sign.manual.motions.length}):`);
  sign.manual.motions.forEach((motion, i) => {
    console.log(`  ${i + 1}. ${motion.type}:`, {
      direction: motion.direction ?? "non spécifiée",
      size: motion.size ?? "non spécifiée",
      repetition: motion.repetition ?? "aucune",
    });
  });

  console.groupEnd();
}

async function testSigml(): Promise<void> {
  console.log("🚀 Phase 2 - Test du parser SiGML");
  console.log("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  
  const files = ["Accept1n.LSF.sigml", "Accident1n.LSF.sigml"];

  for (const name of files) {
    try {
      console.log(`\n📂 Chargement de ${name}...`);
      const xml = await loadSigmlExample(name);
      console.log(`   ✓ Fichier chargé (${xml.length} caractères)`);
      
      console.log(`🔍 Parsing du XML...`);
      const sign = parseSigml(xml);
      console.log(`   ✓ Parsing réussi`);
      
      logSignDetails(name, sign);
    } catch (e) {
      console.error(`❌ Erreur pour ${name}:`, e);
    }
  }

  console.log("\n━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━");
  console.log("✨ Phase 2 terminée : les signes sont parsés en structure Sign");
  console.log("📝 Prochaine étape : Phase 3 - Mapping SiGML → Rig 3D");
}

testSigml();
