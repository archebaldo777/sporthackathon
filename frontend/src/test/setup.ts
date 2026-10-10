import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
// jsdom не реализует эти API, а компоненты их используют
Element.prototype.scrollIntoView = () => {};
window.matchMedia = window.matchMedia || ((() => ({ matches: false, addEventListener() {}, removeEventListener() {} })) as any);
