use std::env;
use std::fs;

/// Reads Meda source file
fn read_file(file_path: String) {
  let contents = fs::read_to_string(file_path)
       .expect("Should have been able to open file");

  println!("Reading file:\n{contents}");
}

fn main() {
  let args: Vec<String> = env::args().collect();

  if args.len() > 2 {
    println!("Usage: rmeda [script]");
  } else if args.len() == 2 {
    let file_path = args[1].to_string();
    read_file(file_path);
  } else {
    println!("> ");
  }
}
