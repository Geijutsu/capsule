{
  description = "Capsule - Beautiful server configuration using Nix";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};
        python = pkgs.python311;
        pythonPackages = python.pkgs;
      in
      {
        packages.default = pythonPackages.buildPythonApplication {
          pname = "capsule";
          version = "0.1.0";

          src = ./.;

          propagatedBuildInputs = with pythonPackages; [
            click
            pyyaml
          ];

          format = "setuptools";

          meta = with pkgs.lib; {
            description = "User-friendly server configuration tool using Nix";
            homepage = "https://github.com/yourusername/capsule";
            license = licenses.mit;
            maintainers = [ ];
          };
        };

        apps.default = {
          type = "app";
          program = "${self.packages.${system}.default}/bin/capsule";
        };

        devShells.default = pkgs.mkShell {
          buildInputs = with pkgs; [
            python
            pythonPackages.click
            pythonPackages.pyyaml
            pythonPackages.pip
            nixos-rebuild
          ];

          shellHook = ''
            echo "🔮 Capsule development environment"
            echo "Run: pip install -e . to install in development mode"
          '';
        };
      }
    );
}
