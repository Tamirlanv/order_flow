import SwaggerUI from "swagger-ui-dist/swagger-ui-bundle";
import "swagger-ui-dist/swagger-ui.css";

SwaggerUI({
  url: "/openapi.json",
  dom_id: "#swagger-ui",
  validatorUrl: null,
  // Mutations belong in the app, which supplies bound CSRF tokens.
  supportedSubmitMethods: [],
  persistAuthorization: false,
});
