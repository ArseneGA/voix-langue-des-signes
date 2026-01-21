import { describe, expect, it } from "vitest";

import { parseSigml } from "../../src/sigml/parser.js";

const SAMPLE_SIGML = `
<sigml>
  <hamgestural_sign gloss="HELLO" lang="BSL">
    <sign_manual>
      <handconfig handshape="flat" thumbpos="open" palmor="f"/>
      <location_bodyarm location="head" side="right_at" />
      <rpt_motion repetition="fromstart">
        <directedmotion direction="o" size="medium" />
      </rpt_motion>
    </sign_manual>
  </hamgestural_sign>
</sigml>
`;

describe("parseSigml", () => {
  it("extrait la structure manuelle d'un signe", () => {
    const sign = parseSigml(SAMPLE_SIGML);

    expect(sign.gloss).toBe("HELLO");
    expect(sign.language).toBe("BSL");
    expect(sign.manual.handConfigurations).toHaveLength(1);
    expect(sign.manual.handConfigurations[0]).toMatchObject({
      hand: "dominant",
      handshape: "flat",
      thumbPos: "open",
      palmor: "f",
    });
    expect(sign.manual.location).toEqual({ body: "head", side: "right_at" });
    expect(sign.manual.motions[0]).toMatchObject({
      type: "directed",
      direction: "o",
      size: "medium",
      repetition: "fromstart",
    });
  });

  it("lève une erreur lorsque le XML est invalide", () => {
    expect(() => parseSigml("<sigml><broken>")).toThrow();
  });
});
