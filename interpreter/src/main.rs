use std::env;
use std::fs;

mod common;
use common::strings::error_messages::UNABLE_TO_OPEN_FILE;
use common::strings::cli::{PROMPT, USAGE_TIP};

/// Run file
fn run_file(file_contents: String) {
  println!("{}", file_contents);
}

/// Reads Meda source file
fn read_file(file_path: String) {
  let contents = fs::read_to_string(file_path)
       .expect(UNABLE_TO_OPEN_FILE);
  
  run_file(contents);
}

/// Run REPL
fn run_repl() {
  println!("{}", PROMPT);
}

fn main() {
  let args: Vec<String> = env::args().collect();
  let too_many_args = args.len() > 2; 
  let correct_num_args = args.len() == 2;

  if too_many_args {
    println!("{}", USAGE_TIP);
  } else if correct_num_args {
    let filepath_arg_index = 1;
    let file_path = args[filepath_arg_index].to_string();

    read_file(file_path);
  } else {
    run_repl();
  }
}
