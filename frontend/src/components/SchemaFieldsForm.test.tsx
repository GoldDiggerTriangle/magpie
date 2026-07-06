import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useState } from "react";
import { beforeEach, expect, test, vi } from "vitest";

import { sanitizeSchemaAttributes, SchemaFieldsForm } from "./SchemaFieldsForm";
import type { CategorySchema } from "../types";

const mocks = vi.hoisted(() => ({
  getCategorySchema: vi.fn()
}));

vi.mock("../api/categories", () => ({
  getCategorySchema: (...args: unknown[]) => mocks.getCategorySchema(...args)
}));

const descriptor: CategorySchema = {
  profile_key: "stamps",
  fields: [
    {
      name: "country",
      label: "Country",
      type: "str",
      required: false,
      choices: [],
      min: null,
      max: null,
      help_text: ""
    },
    {
      name: "year",
      label: "Year",
      type: "int",
      required: false,
      choices: [],
      min: 1840,
      max: 2027,
      help_text: ""
    },
    {
      name: "mint_used",
      label: "Mint/used",
      type: "choice",
      required: false,
      choices: ["mint_never_hinged", "mint_hinged", "used", "cto", "unknown"],
      min: null,
      max: null,
      help_text: ""
    },
    {
      name: "catalogue_refs",
      label: "Catalogue refs",
      type: "list[object]",
      required: false,
      choices: [],
      min: null,
      max: null,
      help_text: "",
      item_shape: {
        system: {
          name: "system",
          label: "System",
          type: "choice",
          required: false,
          choices: ["SG", "Scott", "other"],
          min: null,
          max: null,
          help_text: ""
        },
        number: {
          name: "number",
          label: "Number",
          type: "str",
          required: false,
          choices: [],
          min: null,
          max: null,
          help_text: ""
        }
      }
    }
  ]
};

beforeEach(() => {
  mocks.getCategorySchema.mockResolvedValue(descriptor);
});

function renderForm(schema: CategorySchema = descriptor) {
  mocks.getCategorySchema.mockResolvedValue(schema);
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } }
  });

  function Harness() {
    const [attributes, setAttributes] = useState<Record<string, unknown>>({});
    return (
      <QueryClientProvider client={queryClient}>
        <SchemaFieldsForm categoryId="cat-1" attributes={attributes} onChange={setAttributes} />
        <output data-testid="attrs">{JSON.stringify(attributes)}</output>
      </QueryClientProvider>
    );
  }

  render(<Harness />);
}

test("SchemaFieldsForm renders descriptor field types and repeatable object rows", async () => {
  const user = userEvent.setup();
  renderForm();

  await user.type(await screen.findByLabelText("Country"), "Australia");
  await user.type(screen.getByLabelText("Year"), "1932");
  await user.selectOptions(screen.getByLabelText("Mint/used"), "used");
  await user.click(screen.getByRole("button", { name: /add/i }));
  await user.selectOptions(screen.getByLabelText("System"), "SG");
  await user.type(screen.getByLabelText("Number"), "144");

  await waitFor(() => {
    expect(screen.getByTestId("attrs")).toHaveTextContent("\"country\":\"Australia\"");
    expect(screen.getByTestId("attrs")).toHaveTextContent("\"year\":\"1932\"");
    expect(screen.getByTestId("attrs")).toHaveTextContent("\"mint_used\":\"used\"");
    expect(screen.getByTestId("attrs")).toHaveTextContent("\"catalogue_refs\":[{\"system\":\"SG\",\"number\":\"144\"}]");
  });
});

test("SchemaFieldsForm applies descriptor defaults for gold parity", async () => {
  renderForm({
    profile_key: "gold",
    fields: [
      {
        name: "metal",
        label: "Metal",
        type: "choice",
        required: false,
        choices: ["gold", "silver"],
        min: null,
        max: null,
        help_text: "",
        default: "gold"
      }
    ]
  });

  expect(await screen.findByLabelText("Metal")).toHaveValue("gold");
  await waitFor(() => {
    expect(screen.getByTestId("attrs")).toHaveTextContent("\"metal\":\"gold\"");
  });
});

test("SchemaFieldsForm renders field suggestions as a visible picker with unrestricted custom entry", async () => {
  const user = userEvent.setup();
  renderForm({
    profile_key: "banknotes",
    fields: [
      {
        name: "country",
        label: "Country",
        type: "str",
        required: false,
        choices: [],
        min: null,
        max: null,
        help_text: "",
        suggestions: ["AU", "Australia", "Rhodesia"]
      },
      {
        name: "denomination",
        label: "Denomination",
        type: "str",
        required: false,
        choices: [],
        min: null,
        max: null,
        help_text: "",
        suggestions: ["$1", "$2", "$5", "$10", "$20", "$50", "$100"]
      }
    ]
  });

  const country = await screen.findByLabelText("Country");
  const denomination = screen.getByLabelText("Denomination");
  expect(country.tagName).toBe("SELECT");
  expect(denomination.tagName).toBe("SELECT");
  expect(screen.getAllByText("Other / custom...")).toHaveLength(2);

  await user.selectOptions(denomination, "$10");
  await user.selectOptions(country, "__custom__");
  await user.type(screen.getByLabelText("Country custom value"), "New Hebrides");

  await waitFor(() => {
    expect(screen.getByTestId("attrs")).toHaveTextContent("\"denomination\":\"$10\"");
    expect(screen.getByTestId("attrs")).toHaveTextContent("\"country\":\"New Hebrides\"");
  });
});

test("sanitizeSchemaAttributes removes blank nested rows and trims values", () => {
  expect(sanitizeSchemaAttributes({
    country: " Australia ",
    empty: "",
    catalogue_refs: [{ system: "SG", number: "144" }, { system: "", number: "" }],
    cert: { grader: "PCGS", cert_no: "" }
  })).toEqual({
    country: "Australia",
    catalogue_refs: [{ system: "SG", number: "144" }],
    cert: { grader: "PCGS" }
  });
});
