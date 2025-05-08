{
  description = "uiina :: Using single-instance of IINA when launching through the command line";

  inputs = {
    flake-parts.url = "github:hercules-ci/flake-parts";
    nixpkgs-unstable.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    # TODO: do we need to name it as nixpkgs here?
  };

  outputs =
    { flake-parts, nixpkgs-unstable, ... }@inputs:
    flake-parts.lib.mkFlake { inherit inputs; } {
      imports = [
      ];
      systems = nixpkgs-unstable.lib.platforms.darwin;
      perSystem =
        {
          config,
          self',
          inputs',
          pkgs,
          system,
          ...
        }:
        let
          pythonPackages = pkgs.python313Packages;
        in
        {
          packages.uiina = import ./package.nix {};
          packages.default = config.packages.uiina;
          defaultPackage = config.packages.uiina;

          devShells.default = pkgs.mkShell {
            name = "uiina-dev-env";
            hardeningDisable = ["all"]; # https://discourse.nixos.org/t/why-is-the-nix-compiled-python-slower
            packages = with pkgs; [
              gcc14
              stdenv.cc.cc.lib
              pythonPackages.python
              # pythonPackages.venvShellHook
              pythonPackages.uv

              # non python deps 
              # ... e.g. glib, libz, zlib for numpy ...
              
              iina
              config.packages.uiina
            ];
            # venvDir = "./.venv";
            shellHook = ''
              export PYTHONPATH="$(pwd)"
            '';
            LD_LIBRARY_PATH="${pkgs.stdenv.cc.cc.lib}/lib";
            CMAKE_CXX_COMPILER="${pkgs.gcc14}/bin/:${pkgs.clang_18}/bin/";
          };

          # checks.build = ;

          formatter = pkgs.nixfmt-rfc-style;
        };
      flake = {
      };
    };
}
