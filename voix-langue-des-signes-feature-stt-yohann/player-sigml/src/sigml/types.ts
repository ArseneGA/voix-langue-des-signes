// Représente un signe complet prêt à être utilisé par le Player
export interface Sign {
    gloss: string;
    language?: string; // "BSL", "LSF", etc.
    manual: ManualSign;
    // pour plus tard : nonManual?, timeline?, duration?, rawXml? ...
  }
  
  export interface ManualSign {
    handConfigurations: HandConfiguration[];
    location?: Location;
    motions: Motion[];
    durationMs?: number; // optionnel pour plus tard
  }
  
  // Config d’une main (ou d’un état de main)
  export interface HandConfiguration {
    hand: "dominant" | "non-dominant";
    handshape?: string;
    thumbPos?: string;
    mainBend?: string;
    extfidir?: string; // direction des doigts
    palmor?: string;   // orientation de la paume
    secondHandshape?: string;
    secondThumbpos?: string;
    otherAttributes?: Record<string, string>; // pour garder ce qu’on ne traite pas encore
  }
  
  export interface Location {
    body: string;   // ex: "head", "chest"…
    side?: string;  // ex: "right_at"
  }
  
  // Pour l’instant on ne gère qu’un type de mouvement : directed motion
  export interface Motion {
    type: "directed";
    direction?: string; // "u","d","o","l","r"...
    size?: string;      // "small","medium","large"...
    repetition?: string; // ex: "fromstart"
  }
  