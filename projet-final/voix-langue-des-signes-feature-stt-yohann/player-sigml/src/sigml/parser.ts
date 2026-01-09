import { DOMParser as XmldomParser } from "@xmldom/xmldom";

import type { HandConfiguration, Location, ManualSign, Motion, Sign } from "./types.js";

const KNOWN_HAND_ATTRS = new Set([
  "handshape",
  "thumbpos",
  "mainbend",
  "extfidir",
  "palmor",
  "second_handshape",
  "second_thumbpos",
  "hand",
]);

type ParsedDocument = {
  getElementsByTagName(tag: string): NodeListOf<Element> | HTMLCollectionOf<Element>;
  querySelector(selector: string): Element | null;
  querySelectorAll(selector: string): NodeListOf<Element>;
};

function createDomParser(): { parseFromString(xml: string, mimeType: string): ParsedDocument } {
  if (typeof globalThis.DOMParser !== "undefined") {
    return new globalThis.DOMParser() as unknown as { parseFromString(xml: string, mimeType: string): ParsedDocument };
  }
  return new XmldomParser() as unknown as { parseFromString(xml: string, mimeType: string): ParsedDocument };
}

function ensureDocument(doc: ParsedDocument): void {
  const parserErrors = doc.getElementsByTagName("parsererror");
  const errorCount = "length" in parserErrors ? parserErrors.length : 0;
  if (errorCount > 0) {
    const firstError = parserErrors[0];
    // textContent peut ne pas exister sur tous les types de Document
    let errorMessage = "XML SiGML invalide.";
    if (firstError && "textContent" in firstError) {
      errorMessage = String(firstError.textContent || errorMessage);
    }
    throw new Error(errorMessage);
  }
}

function resolveHand(index: number, attrValue?: string | null): "dominant" | "non-dominant" {
  if (attrValue === "non-dominant") {
    return "non-dominant";
  }
  if (attrValue === "dominant") {
    return "dominant";
  }
  return index === 0 ? "dominant" : "non-dominant";
}

function collectHandConfigurations(manualEl: Element): HandConfiguration[] {
  // Collecter tous les handconfig, même dans split_handconfig ou tgt_motion
  const allHandconfigs = Array.from(manualEl.querySelectorAll("handconfig"));
  
  return allHandconfigs.map((hcEl, index) => {
    const otherAttributes: Record<string, string> = {};

    Array.from(hcEl.attributes).forEach((attr) => {
      if (!KNOWN_HAND_ATTRS.has(attr.name)) {
        otherAttributes[attr.name] = attr.value;
      }
    });

    const handshape = hcEl.getAttribute("handshape");
    const thumbPos = hcEl.getAttribute("thumbpos");
    const mainBend = hcEl.getAttribute("mainbend");
    const extfidir = hcEl.getAttribute("extfidir");
    const palmor = hcEl.getAttribute("palmor");
    const secondHandshape = hcEl.getAttribute("second_handshape");
    const secondThumbpos = hcEl.getAttribute("second_thumbpos");
    
    const config: HandConfiguration = {
      hand: resolveHand(index, hcEl.getAttribute("hand")),
      ...(handshape !== null && { handshape }),
      ...(thumbPos !== null && { thumbPos }),
      ...(mainBend !== null && { mainBend }),
      ...(extfidir !== null && { extfidir }),
      ...(palmor !== null && { palmor }),
      ...(secondHandshape !== null && { secondHandshape }),
      ...(secondThumbpos !== null && { secondThumbpos }),
      ...(Object.keys(otherAttributes).length > 0 && { otherAttributes }),
    };

    return config;
  });
}

function findRepetitionAttribute(node: Element): string | undefined {
  let parent = node.parentNode;
  while (parent && parent.nodeType === Node.ELEMENT_NODE) {
    const elementParent = parent as Element;
    if (elementParent.tagName === "rpt_motion" && elementParent.hasAttribute("repetition")) {
      return elementParent.getAttribute("repetition") ?? undefined;
    }
    parent = elementParent.parentNode;
  }
  return undefined;
}

function collectMotions(manualEl: Element): Motion[] {
  const motionNodes = Array.from(manualEl.getElementsByTagName("directedmotion"));

  return motionNodes.map((motionEl) => {
    const direction = motionEl.getAttribute("direction");
    const size = motionEl.getAttribute("size");
    const repetition = findRepetitionAttribute(motionEl);
    
    return {
      type: "directed" as const,
      ...(direction !== null && { direction }),
      ...(size !== null && { size }),
      ...(repetition !== undefined && { repetition }),
    };
  });
}

export function parseSigml(xml: string): Sign {
  const domParser = createDomParser();
  const doc = domParser.parseFromString(xml, "text/xml");
  ensureDocument(doc);

  const signEl = doc.querySelector("hamgestural_sign");
  if (!signEl) {
    throw new Error("SiGML invalide : <hamgestural_sign> manquant.");
  }

  const gloss = signEl.getAttribute("gloss") ?? "unknown";
  const language = signEl.getAttribute("lang") ?? signEl.getAttribute("xml:lang") ?? undefined;

  const manualEl = signEl.querySelector("sign_manual");
  if (!manualEl) {
    throw new Error("SiGML invalide : <sign_manual> manquant.");
  }

  // Log de debug (en développement uniquement)
  if (typeof console !== "undefined" && console.debug) {
    const hasSplitHandconfig = manualEl.querySelector("split_handconfig") !== null;
    const hasSplitLocation = manualEl.querySelector("split_location") !== null;
    const hasParMotion = manualEl.querySelector("par_motion") !== null;
    const hasTgtMotion = manualEl.querySelector("tgt_motion") !== null;
    
    if (hasSplitHandconfig || hasSplitLocation || hasParMotion || hasTgtMotion) {
      console.debug("🔍 Structures SiGML complexes détectées:", {
        split_handconfig: hasSplitHandconfig,
        split_location: hasSplitLocation,
        par_motion: hasParMotion,
        tgt_motion: hasTgtMotion,
      });
    }
  }

  const handConfigurations = collectHandConfigurations(manualEl);

  // Gérer split_location (plusieurs location_bodyarm) ou location_bodyarm unique
  let location: Location | undefined;
  const allLocations = Array.from(manualEl.querySelectorAll("location_bodyarm"));
  if (allLocations.length > 0) {
    // Pour l'instant, on prend la première location (Phase 2 = parsing basique)
    // Phase 3+ pourra gérer les locations multiples/complexes
    const locEl = allLocations[0];
    if (locEl) {
      const body = locEl.getAttribute("location") ?? "neutral";
      const side = locEl.getAttribute("side");
      location = {
        body,
        ...(side !== null && { side }),
      };
    }
  }

  const motions = collectMotions(manualEl);

  const manual: ManualSign = {
    handConfigurations,
    ...(location !== undefined && { location }),
    motions,
  };

  return {
    gloss,
    ...(language !== undefined && { language }),
    manual,
  };
}
