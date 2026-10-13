declare module "swagger-ui-dist/swagger-ui-bundle" {
  export default function SwaggerUI(options: {
    url: string;
    dom_id: string;
    validatorUrl: null;
    supportedSubmitMethods: string[];
    persistAuthorization: boolean;
  }): void;
}
